#!/usr/bin/env python3
"""Phase K: Final deep-project claim audit.

Audits every major claim against its evidence artifact.
Reports: supported / partially supported / not supported.
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

PROJECT_ROOT = Path(__file__).resolve().parent.parent


CLAIMS = [
    {
        "claim_id": "C1",
        "claim": "ARC static portfolio solves ~95/1000 with DSL",
        "category": "performance",
        "evidence_phase": "A",
        "artifact_path": "outputs/full_arc1000_novel_pipeline/progress.jsonl",
        "check_type": "count_field",
        "check_field": "solved_by_dsl",
        "check_threshold": 80,
        "paper_section": "Results: ARC Evaluation",
    },
    {
        "claim_id": "C2",
        "claim": "ARC static portfolio solves ~84/1000 without DSL",
        "category": "performance",
        "evidence_phase": "A",
        "artifact_path": "outputs/full_arc1000_novel_pipeline/progress.jsonl",
        "check_type": "count_field",
        "check_field": "solved_by_static",
        "check_threshold": 70,
        "paper_section": "Results: ARC Evaluation",
    },
    {
        "claim_id": "C3",
        "claim": "ConceptARC ~12/160",
        "category": "performance",
        "evidence_phase": "B",
        "artifact_path": "outputs/deep_project_completion/cross_domain_adapter_genesis/adapter_genesis_results.csv",
        "check_type": "file_exists",
        "paper_section": "Results: Cross-Domain",
    },
    {
        "claim_id": "C4",
        "claim": "Four verified real ARC promotions with 0 FP",
        "category": "core",
        "evidence_phase": "A",
        "artifact_path": "outputs/full_arc1000_novel_pipeline/progress.jsonl",
        "check_type": "zero_fp",
        "paper_section": "Results: Operator Promotion",
    },
    {
        "claim_id": "C5",
        "claim": "AdapterGenesis synthesizes usable cross-domain adapters",
        "category": "architecture",
        "evidence_phase": "B",
        "artifact_path": "outputs/deep_project_completion/cross_domain_adapter_genesis/summary.md",
        "check_type": "summary_exists",
        "paper_section": "Results: AdapterGenesis",
    },
    {
        "claim_id": "C6",
        "claim": "Cross-domain operator transfer",
        "category": "architecture",
        "evidence_phase": "C",
        "artifact_path": "outputs/deep_project_completion/cross_domain_operator_transfer/transfer_matrix.csv",
        "check_type": "file_exists",
        "paper_section": "Results: Operator Transfer",
    },
    {
        "claim_id": "C7",
        "claim": "Cumulative memory improves solve rate",
        "category": "learning",
        "evidence_phase": "D",
        "artifact_path": "outputs/deep_project_completion/memory_growth_deep/stage_metrics.csv",
        "check_type": "memory_improvement",
        "paper_section": "Results: Cumulative Learning",
    },
    {
        "claim_id": "C8",
        "claim": "Many-to-few grouping operators",
        "category": "frontier",
        "evidence_phase": "E",
        "artifact_path": "outputs/deep_project_completion/many_to_few_grouping/real_arc_results.csv",
        "check_type": "file_exists",
        "paper_section": "Results: Frontier Operators",
    },
    {
        "claim_id": "C9",
        "claim": "Shape completion operators",
        "category": "frontier",
        "evidence_phase": "F",
        "artifact_path": "outputs/deep_project_completion/shape_completion/real_arc_results.csv",
        "check_type": "file_exists",
        "paper_section": "Results: Frontier Operators",
    },
    {
        "claim_id": "C10",
        "claim": "Position-within-object recolor operators",
        "category": "frontier",
        "evidence_phase": "G",
        "artifact_path": "outputs/deep_project_completion/position_within_object_recolor/real_arc_results.csv",
        "check_type": "file_exists",
        "paper_section": "Results: Frontier Operators",
    },
    {
        "claim_id": "C11",
        "claim": "Neural modules improve verified pipeline",
        "category": "neural",
        "evidence_phase": "H",
        "artifact_path": "outputs/deep_project_completion/neural_operator_proposal/summary.md",
        "check_type": "summary_exists",
        "paper_section": "Results: Neural Advisory",
    },
    {
        "claim_id": "C12",
        "claim": "Certificates are machine-checkable",
        "category": "verification",
        "evidence_phase": "I",
        "artifact_path": "outputs/deep_project_completion/formal_checker_feasibility/formal_checker_feasibility_report.md",
        "check_type": "summary_exists",
        "paper_section": "Methods: Verification",
    },
    {
        "claim_id": "C13",
        "claim": "Full reproducibility",
        "category": "infrastructure",
        "evidence_phase": "J",
        "artifact_path": "outputs/deep_project_completion/reproducibility_package/artifact_manifest.md",
        "check_type": "file_exists",
        "paper_section": "Supplementary",
    },
]


def check_count_field(artifact_path: Path, field: str, threshold: int) -> dict:
    if not artifact_path.exists():
        return {"status": "not_supported", "reason": "artifact not found", "value": None}
    count = 0
    total = 0
    with open(artifact_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                total += 1
                if entry.get(field):
                    count += 1
            except json.JSONDecodeError:
                continue
    if total < 100:
        return {"status": "partially_supported", "reason": f"only {total} entries (run incomplete)", "value": count}
    if count >= threshold:
        return {"status": "supported", "reason": f"{count}/{total} (threshold={threshold})", "value": count}
    return {"status": "partially_supported", "reason": f"{count}/{total} below threshold {threshold}", "value": count}


def check_zero_fp(artifact_path: Path) -> dict:
    if not artifact_path.exists():
        return {"status": "not_supported", "reason": "artifact not found", "value": None}
    fp_count = 0
    promoted_count = 0
    total = 0
    with open(artifact_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                total += 1
                if entry.get("false_positive"):
                    fp_count += 1
                if entry.get("operator_promoted"):
                    promoted_count += 1
            except json.JSONDecodeError:
                continue
    if fp_count == 0 and promoted_count > 0:
        return {"status": "supported", "reason": f"0 FP across {total} entries, {promoted_count} promotions", "value": 0}
    elif fp_count == 0 and promoted_count == 0:
        return {"status": "partially_supported", "reason": f"0 FP but 0 promotions so far ({total} entries)", "value": 0}
    else:
        return {"status": "not_supported", "reason": f"{fp_count} FP detected!", "value": fp_count}


def check_file_exists(artifact_path: Path) -> dict:
    if artifact_path.exists():
        size = artifact_path.stat().st_size
        if size > 100:
            return {"status": "supported", "reason": f"artifact exists ({size} bytes)", "value": size}
        return {"status": "partially_supported", "reason": f"artifact exists but small ({size} bytes)", "value": size}
    return {"status": "not_supported", "reason": "artifact not found — experiment not yet run", "value": None}


def check_summary_exists(artifact_path: Path) -> dict:
    if not artifact_path.exists():
        return {"status": "not_supported", "reason": "summary not found — experiment not yet run", "value": None}
    with open(artifact_path) as f:
        content = f.read()
    if "not supported" in content.lower() or "not_supported" in content.lower():
        return {"status": "not_supported", "reason": "summary indicates claim not supported", "value": None}
    if "partially" in content.lower():
        return {"status": "partially_supported", "reason": "summary indicates partial support", "value": None}
    return {"status": "supported", "reason": "summary exists with content", "value": len(content)}


def check_memory_improvement(artifact_path: Path) -> dict:
    if not artifact_path.exists():
        return {"status": "not_supported", "reason": "metrics not found", "value": None}
    import csv as csv_mod
    with open(artifact_path) as f:
        reader = csv_mod.DictReader(f)
        rows = list(reader)
    if not rows:
        return {"status": "not_supported", "reason": "empty metrics", "value": None}
    baseline = int(rows[0].get("tasks_solved", 0)) if rows else 0
    final = int(rows[-1].get("tasks_solved", 0)) if rows else 0
    resumed = sum(int(r.get("previously_failed_now_solved", 0)) for r in rows)
    if resumed > 0:
        return {"status": "supported", "reason": f"baseline={baseline}, final stage={final}, resumed={resumed}", "value": resumed}
    if final > baseline:
        return {"status": "partially_supported", "reason": f"baseline={baseline}, final={final}, but no resumed tasks", "value": final - baseline}
    return {"status": "not_supported", "reason": f"no improvement: baseline={baseline}, final={final}", "value": 0}


def audit_claim(claim: dict) -> dict:
    artifact_path = PROJECT_ROOT / claim["artifact_path"]
    check_type = claim["check_type"]

    if check_type == "count_field":
        result = check_count_field(artifact_path, claim["check_field"], claim["check_threshold"])
    elif check_type == "zero_fp":
        result = check_zero_fp(artifact_path)
    elif check_type == "file_exists":
        result = check_file_exists(artifact_path)
    elif check_type == "summary_exists":
        result = check_summary_exists(artifact_path)
    elif check_type == "memory_improvement":
        result = check_memory_improvement(artifact_path)
    else:
        result = {"status": "unknown", "reason": f"unknown check type: {check_type}", "value": None}

    return {**claim, **result}


FORBIDDEN_WORDINGS = {
    "C1": "Broadly solves ARC; Solves most ARC tasks",
    "C4": "Proves correctness; Mathematically verified",
    "C5": "Automatic domain adaptation works broadly; Universal adapter synthesis",
    "C6": "Universal operator transfer; Operators generalize to any domain",
    "C7": "Learns like humans; AGI-level learning",
    "C8": "Solves grouping broadly; Complete grouping solution",
    "C9": "Solves completion broadly",
    "C11": "Neural modules cause promotions (unless demonstrated)",
    "C12": "Theorem-prover-level proof (unless implemented)",
}


def main():
    parser = argparse.ArgumentParser(description="Final deep-project claim audit")
    parser.add_argument("--output-dir", default="outputs/deep_project_completion/final_claim_audit")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== Final Deep-Project Claim Audit ===")

    results = []
    for claim in CLAIMS:
        print(f"  Checking {claim['claim_id']}: {claim['claim'][:50]}...")
        result = audit_claim(claim)
        results.append(result)

    # Write CSV
    with open(output_dir / "final_claim_audit.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "claim_id", "claim", "category", "evidence_phase", "status",
            "reason", "value", "paper_section",
        ])
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k) for k in writer.fieldnames})

    # Write markdown
    supported = [r for r in results if r["status"] == "supported"]
    partial = [r for r in results if r["status"] == "partially_supported"]
    not_supported = [r for r in results if r["status"] == "not_supported"]

    lines = [
        "# Final Deep-Project Claim Audit",
        f"\nGenerated: {datetime.now().isoformat()}",
        "",
        f"## Summary: {len(supported)} supported, {len(partial)} partial, {len(not_supported)} not supported",
        "",
        "## Detailed Results",
        "",
        "| ID | Claim | Status | Evidence |",
        "|----|-------|--------|----------|",
    ]
    for r in results:
        status_icon = {"supported": "SUPPORTED", "partially_supported": "PARTIAL", "not_supported": "NOT SUPPORTED"}.get(r["status"], "?")
        lines.append(f"| {r['claim_id']} | {r['claim'][:60]} | {status_icon} | {r['reason'][:60]} |")

    lines += ["", "## Allowed Claims", ""]
    for r in supported:
        lines.append(f"- **{r['claim_id']}**: {r['claim']} — {r['reason']}")

    lines += ["", "## Partially Supported (qualify in paper)", ""]
    for r in partial:
        lines.append(f"- **{r['claim_id']}**: {r['claim']} — {r['reason']}")

    lines += ["", "## Not Supported (do NOT claim)", ""]
    for r in not_supported:
        lines.append(f"- **{r['claim_id']}**: {r['claim']} — {r['reason']}")

    lines += ["", "## Forbidden Wordings", ""]
    for cid, forbidden in FORBIDDEN_WORDINGS.items():
        lines.append(f"- **{cid}**: Do NOT write: \"{forbidden}\"")

    with open(output_dir / "final_claim_audit.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    # Allowed claims
    with open(output_dir / "allowed_claims.md", "w") as f:
        f.write("# Allowed Claims\n\n")
        for r in supported + partial:
            qualifier = "" if r["status"] == "supported" else " (qualify)"
            f.write(f"- {r['claim_id']}{qualifier}: {r['claim']}\n")

    # Forbidden claims
    with open(output_dir / "forbidden_claims.md", "w") as f:
        f.write("# Forbidden Claims\n\n")
        for r in not_supported:
            f.write(f"- {r['claim_id']}: {r['claim']} — {r['reason']}\n")
        f.write("\n## Forbidden Wordings\n\n")
        for cid, forbidden in FORBIDDEN_WORDINGS.items():
            f.write(f"- {cid}: \"{forbidden}\"\n")

    with open(output_dir / "status.json", "w") as f:
        json.dump({"status": "completed", "generated": datetime.now().isoformat(),
                    "supported": len(supported), "partial": len(partial),
                    "not_supported": len(not_supported)}, f)

    print(f"\nResults: {len(supported)} supported, {len(partial)} partial, {len(not_supported)} not supported")
    print(f"Written to {output_dir}/")


if __name__ == "__main__":
    main()
