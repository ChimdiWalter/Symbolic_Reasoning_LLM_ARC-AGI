#!/usr/bin/env python3
"""Phase J: Build reproducibility package.

Generates artifact manifest, reproduction commands, environment report,
dataset manifest, script dependency graph, and claim-to-artifact mapping.
"""
import argparse
import csv
import importlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_env_report() -> dict:
    info = {
        "python_version": sys.version,
        "platform": sys.platform,
        "hostname": os.uname().nodename,
        "generated": datetime.now().isoformat(),
    }
    try:
        result = subprocess.run(["pip", "list", "--format=json"], capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            info["packages"] = json.loads(result.stdout)
    except Exception:
        info["packages"] = []

    venv = os.environ.get("VIRTUAL_ENV", "none")
    info["virtualenv"] = venv

    for mod_name in ["numpy", "torch", "gudhi", "cvxpy", "sklearn", "scipy", "z3"]:
        try:
            m = importlib.import_module(mod_name)
            info[f"{mod_name}_version"] = getattr(m, "__version__", "installed")
        except ImportError:
            info[f"{mod_name}_version"] = "NOT INSTALLED"
    return info


def build_artifact_manifest(output_dir: Path) -> list:
    artifacts = []
    key_dirs = [
        ("outputs/full_arc1000_novel_pipeline", "ARC-1000 clean run (job 14020393)"),
        ("outputs/deep_project_completion/cross_domain_adapter_genesis", "Phase B: cross-domain AdapterGenesis"),
        ("outputs/deep_project_completion/cross_domain_operator_transfer", "Phase C: operator transfer"),
        ("outputs/deep_project_completion/memory_growth_deep", "Phase D: memory growth"),
        ("outputs/deep_project_completion/many_to_few_grouping", "Phase E: many-to-few"),
        ("outputs/deep_project_completion/shape_completion", "Phase F: shape completion"),
        ("outputs/deep_project_completion/position_within_object_recolor", "Phase G: position recolor"),
        ("outputs/deep_project_completion/neural_operator_proposal", "Phase H: neural proposals"),
        ("outputs/deep_project_completion/formal_checker_feasibility", "Phase I: formal checker"),
        ("outputs/deep_project_completion/reproducibility_package", "Phase J: this package"),
        ("outputs/deep_project_completion/final_claim_audit", "Phase K: claim audit"),
    ]
    for rel_path, desc in key_dirs:
        full = PROJECT_ROOT / rel_path
        exists = full.exists()
        file_count = len(list(full.rglob("*"))) if exists else 0
        artifacts.append({
            "path": rel_path,
            "description": desc,
            "exists": exists,
            "file_count": file_count,
        })

    key_files = [
        ("outputs/full_arc1000_novel_pipeline/progress.jsonl", "ARC-1000 progress log"),
        ("outputs/full_arc1000_novel_pipeline/certificates/2a5f8217.json", "Verified certificate: 2a5f8217"),
        ("outputs/full_arc1000_novel_pipeline/known_task_guard.jsonl", "Known-task guard log"),
        ("outputs/deep_project_completion/master_status.md", "Master status"),
        ("outputs/deep_project_completion/master_claim_table.csv", "Claim table"),
        ("outputs/deep_project_completion/master_job_table.csv", "Job table"),
    ]
    for rel_path, desc in key_files:
        full = PROJECT_ROOT / rel_path
        artifacts.append({
            "path": rel_path,
            "description": desc,
            "exists": full.exists(),
            "file_count": 1 if full.exists() else 0,
        })
    return artifacts


def build_dataset_manifest() -> list:
    datasets = []
    arc_root = PROJECT_ROOT / "data" / "arc"
    for name in ["arc-agi_training_challenges.json", "arc-agi_evaluation_challenges.json",
                  "arc-agi_training_solutions.json", "arc-agi_evaluation_solutions.json",
                  "arc-agi_test_challenges.json"]:
        p = arc_root / name
        datasets.append({
            "name": name,
            "path": f"data/arc/{name}",
            "exists": p.exists(),
            "size_bytes": p.stat().st_size if p.exists() else 0,
        })
    conceptarc = PROJECT_ROOT / "data" / "conceptarc"
    datasets.append({
        "name": "ConceptARC",
        "path": "data/conceptarc/",
        "exists": conceptarc.exists(),
        "size_bytes": sum(f.stat().st_size for f in conceptarc.rglob("*") if f.is_file()) if conceptarc.exists() else 0,
    })
    return datasets


def build_script_deps() -> list:
    scripts_dir = PROJECT_ROOT / "scripts"
    deps = []
    for script in sorted(scripts_dir.glob("*.py")):
        imports = set()
        try:
            with open(script) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("from reasoning_project"):
                        mod = line.split("import")[0].replace("from ", "").strip()
                        imports.add(mod)
                    elif line.startswith("import reasoning_project"):
                        imports.add(line.split()[1])
        except Exception:
            pass
        deps.append({
            "script": script.name,
            "imports": sorted(imports),
        })
    return deps


def build_claim_to_artifact_map() -> list:
    return [
        {"claim_id": "C1", "claim": "ARC static portfolio ~95/1000 with DSL", "artifact": "outputs/full_arc1000_novel_pipeline/progress.jsonl", "verification": "grep solved_by_dsl progress.jsonl | wc -l"},
        {"claim_id": "C2", "claim": "ARC static portfolio ~84/1000 without DSL", "artifact": "outputs/full_arc1000_novel_pipeline/progress.jsonl", "verification": "grep solved_by_static progress.jsonl | wc -l"},
        {"claim_id": "C3", "claim": "ConceptARC ~12/160", "artifact": "outputs/deep_project_completion/cross_domain_adapter_genesis/adapter_genesis_results.csv", "verification": "grep conceptarc adapter_genesis_results.csv"},
        {"claim_id": "C4", "claim": "Four verified promotions, 0 FP", "artifact": "outputs/full_arc1000_novel_pipeline/certificates/", "verification": "ls certificates/ && grep false_positive progress.jsonl"},
        {"claim_id": "C5", "claim": "AdapterGenesis cross-domain", "artifact": "outputs/deep_project_completion/cross_domain_adapter_genesis/summary.md", "verification": "cat summary.md"},
        {"claim_id": "C6", "claim": "Cross-domain operator transfer", "artifact": "outputs/deep_project_completion/cross_domain_operator_transfer/transfer_matrix.csv", "verification": "cat transfer_matrix.csv"},
        {"claim_id": "C7", "claim": "Memory growth helps", "artifact": "outputs/deep_project_completion/memory_growth_deep/stage_metrics.csv", "verification": "cat stage_metrics.csv"},
        {"claim_id": "C8", "claim": "Many-to-few grouping", "artifact": "outputs/deep_project_completion/many_to_few_grouping/real_arc_results.csv", "verification": "cat real_arc_results.csv"},
        {"claim_id": "C9", "claim": "Shape completion", "artifact": "outputs/deep_project_completion/shape_completion/real_arc_results.csv", "verification": "cat real_arc_results.csv"},
        {"claim_id": "C10", "claim": "Position recolor", "artifact": "outputs/deep_project_completion/position_within_object_recolor/real_arc_results.csv", "verification": "cat real_arc_results.csv"},
        {"claim_id": "C11", "claim": "Neural modules improve pipeline", "artifact": "outputs/deep_project_completion/neural_operator_proposal/summary.md", "verification": "cat summary.md"},
        {"claim_id": "C12", "claim": "Formal verification", "artifact": "outputs/deep_project_completion/formal_checker_feasibility/formal_checker_feasibility_report.md", "verification": "cat formal_checker_feasibility_report.md"},
        {"claim_id": "C13", "claim": "Full reproducibility", "artifact": "outputs/deep_project_completion/reproducibility_package/", "verification": "bash run_all_smoke_tests.sh"},
    ]


def write_reproduction_commands(output_dir: Path):
    content = """# Reproduction Commands

## Environment Setup

```bash
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
```

## Run Test Suite

```bash
python3.11 -m pytest tests/ -x -q
```

## Run Phase A: Monitor ARC-1000

```bash
python3.11 scripts/monitor_arc1000_run.py
```

## Run Phase B: Cross-Domain AdapterGenesis

```bash
python3.11 scripts/audit_cross_domain_capabilities.py --output-dir outputs/deep_project_completion/cross_domain_adapter_genesis
python3.11 scripts/run_adapter_genesis_deep_eval.py --output-dir outputs/deep_project_completion/cross_domain_adapter_genesis
```

## Run Phase C: Cross-Domain Operator Transfer

```bash
python3.11 scripts/run_cross_domain_operator_transfer_deep.py --output-dir outputs/deep_project_completion/cross_domain_operator_transfer
```

## Run Phase D: Memory Growth

```bash
python3.11 scripts/run_deep_memory_growth_curriculum.py --output-dir outputs/deep_project_completion/memory_growth_deep
```

## Run Phase E: Many-to-Few Grouping

```bash
python3.11 scripts/test_many_to_few_grouping_microcycle.py --output-dir outputs/deep_project_completion/many_to_few_grouping
python3.11 scripts/run_many_to_few_real_arc.py --output-dir outputs/deep_project_completion/many_to_few_grouping
```

## Run Phase F: Shape Completion

```bash
python3.11 scripts/test_shape_completion_microcycle.py --output-dir outputs/deep_project_completion/shape_completion
python3.11 scripts/run_shape_completion_real_arc.py --output-dir outputs/deep_project_completion/shape_completion
```

## Run Phase G: Position-Within-Object Recolor

```bash
python3.11 scripts/test_position_within_object_recolor_microcycle.py --output-dir outputs/deep_project_completion/position_within_object_recolor
python3.11 scripts/run_position_within_object_recolor_real_arc.py --output-dir outputs/deep_project_completion/position_within_object_recolor
```

## Run Phase H: Neural Operator Proposal

```bash
python3.11 scripts/run_neural_operator_proposal_deep.py --output-dir outputs/deep_project_completion/neural_operator_proposal
```

## Run Phase I: Certificate Checker

```bash
python3.11 scripts/build_certificate_checker_feasibility.py --output-dir outputs/deep_project_completion/formal_checker_feasibility
```

## Run Phase K: Final Claim Audit

```bash
python3.11 scripts/build_final_deep_project_claim_audit.py --output-dir outputs/deep_project_completion/final_claim_audit
```

## Regenerate All Tables

```bash
bash outputs/deep_project_completion/reproducibility_package/regenerate_all_tables.sh
```

## Verify All Certificates

```bash
bash outputs/deep_project_completion/reproducibility_package/verify_all_certificates.sh
```
"""
    with open(output_dir / "reproduction_commands.md", "w") as f:
        f.write(content)


def write_smoke_test_script(output_dir: Path):
    content = """#!/bin/bash
set -euo pipefail
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

echo "=== Smoke Tests ==="
echo "1. Test suite..."
python3.11 -m pytest tests/ -x -q --timeout=120 2>&1 | tail -5

echo "2. ARC smoke..."
python3.11 scripts/run_arc_smoke.py --max-tasks 5 2>&1 | tail -3

echo "3. Monitor script..."
python3.11 scripts/monitor_arc1000_run.py 2>&1 | tail -5

echo "4. Import check..."
python3.11 -c "
from reasoning_project.reasoning_engine import StructuralReasoner, GridDomainAdapter
from reasoning_project.adapter_genesis import AdapterGenesis
from reasoning_project.near_solved_memory import NearSolvedMemory
from reasoning_project.operator_invention import OperatorInventor
from reasoning_project.certificates import CertificateBuilder
from reasoning_project.many_to_few_grouping import ManyToFewOperator
from reasoning_project.shape_completion import ShapeCompletionOperator
from reasoning_project.position_within_object_recolor import PositionRecolorOperator
print('All imports OK')
"

echo "=== All smoke tests passed ==="
"""
    path = output_dir / "run_all_smoke_tests.sh"
    with open(path, "w") as f:
        f.write(content)
    os.chmod(path, 0o755)


def write_regenerate_tables_script(output_dir: Path):
    content = """#!/bin/bash
set -euo pipefail
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

echo "=== Regenerating tables ==="

echo "1. Monitor report..."
python3.11 scripts/monitor_arc1000_run.py

echo "2. Claim audit..."
python3.11 scripts/build_final_deep_project_claim_audit.py --output-dir outputs/deep_project_completion/final_claim_audit 2>&1 | tail -5

echo "=== Done ==="
"""
    path = output_dir / "regenerate_all_tables.sh"
    with open(path, "w") as f:
        f.write(content)
    os.chmod(path, 0o755)


def write_verify_certificates_script(output_dir: Path):
    content = """#!/bin/bash
set -euo pipefail
cd /cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project
source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate

echo "=== Verifying certificates ==="
python3.11 scripts/build_certificate_checker_feasibility.py --output-dir outputs/deep_project_completion/formal_checker_feasibility
echo "=== Done ==="
"""
    path = output_dir / "verify_all_certificates.sh"
    with open(path, "w") as f:
        f.write(content)
    os.chmod(path, 0o755)


def main():
    parser = argparse.ArgumentParser(description="Build reproducibility package")
    parser.add_argument("--output-dir", default="outputs/deep_project_completion/reproducibility_package")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== Building Reproducibility Package ===")

    # Environment report
    print("1. Environment report...")
    env = get_env_report()
    with open(output_dir / "environment_report.md", "w") as f:
        f.write("# Environment Report\n\n")
        f.write(f"Generated: {env['generated']}\n\n")
        f.write(f"- Python: {env['python_version']}\n")
        f.write(f"- Platform: {env['platform']}\n")
        f.write(f"- Hostname: {env['hostname']}\n")
        f.write(f"- Virtualenv: {env['virtualenv']}\n\n")
        for key in ["numpy", "torch", "gudhi", "cvxpy", "sklearn", "scipy", "z3"]:
            f.write(f"- {key}: {env.get(f'{key}_version', 'unknown')}\n")

    # Artifact manifest
    print("2. Artifact manifest...")
    artifacts = build_artifact_manifest(output_dir)
    with open(output_dir / "artifact_manifest.md", "w") as f:
        f.write("# Artifact Manifest\n\n")
        f.write("| Path | Description | Exists | Files |\n")
        f.write("|------|-------------|--------|-------|\n")
        for a in artifacts:
            f.write(f"| {a['path']} | {a['description']} | {a['exists']} | {a['file_count']} |\n")

    # Dataset manifest
    print("3. Dataset manifest...")
    datasets = build_dataset_manifest()
    with open(output_dir / "dataset_manifest.md", "w") as f:
        f.write("# Dataset Manifest\n\n")
        f.write("| Name | Path | Exists | Size |\n")
        f.write("|------|------|--------|------|\n")
        for d in datasets:
            size_mb = round(d["size_bytes"] / 1024 / 1024, 2)
            f.write(f"| {d['name']} | {d['path']} | {d['exists']} | {size_mb} MB |\n")

    # Script dependency graph
    print("4. Script dependencies...")
    deps = build_script_deps()
    with open(output_dir / "script_dependency_graph.md", "w") as f:
        f.write("# Script Dependency Graph\n\n")
        for d in deps:
            f.write(f"## {d['script']}\n")
            if d["imports"]:
                for imp in d["imports"]:
                    f.write(f"  - {imp}\n")
            else:
                f.write("  (no reasoning_project imports)\n")
            f.write("\n")

    # Claim-to-artifact map
    print("5. Claim-to-artifact map...")
    claim_map = build_claim_to_artifact_map()
    with open(output_dir / "claim_to_artifact_map.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["claim_id", "claim", "artifact", "verification"])
        writer.writeheader()
        for row in claim_map:
            writer.writerow(row)

    # Shell scripts
    print("6. Shell scripts...")
    write_reproduction_commands(output_dir)
    write_smoke_test_script(output_dir)
    write_regenerate_tables_script(output_dir)
    write_verify_certificates_script(output_dir)

    with open(output_dir / "status.json", "w") as f:
        json.dump({"status": "completed", "generated": datetime.now().isoformat()}, f)

    print(f"Package written to {output_dir}/")
    print("=== Done ===")


if __name__ == "__main__":
    main()
