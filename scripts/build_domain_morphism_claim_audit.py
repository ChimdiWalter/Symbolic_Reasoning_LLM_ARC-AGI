#!/usr/bin/env python3.11
"""Phase 9: Domain-morphism claim audit."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path("/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project")

CLAIMS = [
    {
        "id": "DM1",
        "text": "Domain signatures can be extracted from adapters.",
        "evidence_files": ["microcycle/results.csv", "adapter_signature_compiler/signature_comparison.csv"],
        "check": "signatures_extracted",
    },
    {
        "id": "DM2",
        "text": "Domain morphisms can be proposed symbolically.",
        "evidence_files": ["microcycle/results.csv"],
        "check": "morphisms_proposed",
    },
    {
        "id": "DM3",
        "text": "Morphism proof obligations can be checked.",
        "evidence_files": ["microcycle/results.csv"],
        "check": "obligations_checked",
    },
    {
        "id": "DM4",
        "text": "Abstract operators can instantiate across domains.",
        "evidence_files": ["microcycle/results.csv"],
        "check": "operators_instantiated",
    },
    {
        "id": "DM5",
        "text": "Morphism certificates can be emitted.",
        "evidence_files": ["microcycle/results.csv"],
        "check": "certificates_emitted",
    },
    {
        "id": "DM6",
        "text": "Memory can store and retrieve abstract operator schemas.",
        "evidence_files": ["memory_microcycle/summary.md"],
        "check": "memory_works",
    },
    {
        "id": "DM7",
        "text": "Neural/VLM can propose morphisms.",
        "evidence_files": ["neural_morphism_proposal/proposals.csv"],
        "check": "neural_proposes",
    },
    {
        "id": "DM8",
        "text": "AdapterGenesis can serve as domain-signature compiler.",
        "evidence_files": ["adapter_signature_compiler/signature_comparison.csv"],
        "check": "adapter_genesis_compiles",
    },
    {
        "id": "DM9",
        "text": "Cross-domain transfer is improved by morphism learning.",
        "evidence_files": ["existing_transfer_as_morphisms.csv", "microcycle/results.csv"],
        "check": "transfer_improved",
    },
    {
        "id": "DM10",
        "text": "Broad automatic domain adaptation is not yet proven unless supported.",
        "evidence_files": [],
        "check": "honest_negative",
    },
]


def read_csv_safe(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def read_text_safe(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def check_claim(claim: Dict, base: Path) -> Dict[str, Any]:
    cid = claim["id"]
    result = {
        "claim_id": cid,
        "claim_text": claim["text"],
        "status": "not_supported",
        "evidence_file": "",
        "allowed_wording": "",
        "forbidden_wording": "",
    }

    check = claim["check"]

    if check == "signatures_extracted":
        micro = read_csv_safe(base / "microcycle/results.csv")
        sig_csv = read_csv_safe(base / "adapter_signature_compiler/signature_comparison.csv")
        if micro or sig_csv:
            result["status"] = "supported"
            result["evidence_file"] = "microcycle/results.csv, adapter_signature_compiler/signature_comparison.csv"
            result["allowed_wording"] = "Domain signatures can be extracted from hand-coded and synthesized adapters"
        else:
            result["allowed_wording"] = "Signature extraction was not tested"
        result["forbidden_wording"] = "Signatures are automatically discovered from raw data"

    elif check == "morphisms_proposed":
        micro = read_csv_safe(base / "microcycle/results.csv")
        if micro and any(r.get("morphism_score", "0") != "0.000" for r in micro):
            result["status"] = "supported"
            result["evidence_file"] = "microcycle/results.csv"
            result["allowed_wording"] = "Symbolic morphisms can be proposed between typed domain signatures"
        result["forbidden_wording"] = "Morphisms are learned automatically from data"

    elif check == "obligations_checked":
        micro = read_csv_safe(base / "microcycle/results.csv")
        if micro and any("/" in r.get("obligations_passed", "") for r in micro):
            result["status"] = "supported"
            result["evidence_file"] = "microcycle/results.csv"
            result["allowed_wording"] = "8 proof obligation categories can be machine-checked"
        result["forbidden_wording"] = "Morphisms are formally verified"

    elif check == "operators_instantiated":
        micro = read_csv_safe(base / "microcycle/results.csv")
        certified = [r for r in micro if r.get("certified") == "True"]
        if certified:
            result["status"] = "supported"
            result["evidence_file"] = "microcycle/results.csv"
            result["allowed_wording"] = (
                f"Abstract operators instantiated across {len(certified)} domain-operator pairs "
                "under typed morphisms"
            )
        elif micro:
            result["status"] = "partial"
            result["allowed_wording"] = "Instantiation attempted but not all pairs certified"
        result["forbidden_wording"] = "Operators transfer automatically to arbitrary domains"

    elif check == "certificates_emitted":
        cert_dir = base / "microcycle/certificates"
        certs = list(cert_dir.glob("*.json")) if cert_dir.exists() else []
        if certs:
            result["status"] = "supported"
            result["evidence_file"] = f"microcycle/certificates/ ({len(certs)} certificates)"
            result["allowed_wording"] = f"{len(certs)} morphism certificates emitted with proof obligations"
        result["forbidden_wording"] = "All transfers are certified"

    elif check == "memory_works":
        summary = read_text_safe(base / "memory_microcycle/summary.md")
        if "Schema retrieved from memory**: True" in summary:
            result["status"] = "supported"
            result["evidence_file"] = "memory_microcycle/summary.md"
            result["allowed_wording"] = "Memory can store and retrieve abstract operator schemas across domains"
        elif summary:
            result["status"] = "partial"
            result["allowed_wording"] = "Memory stores schemas but retrieval quality varies"
        result["forbidden_wording"] = "Memory enables broad cumulative domain transfer"

    elif check == "neural_proposes":
        props = read_csv_safe(base / "neural_morphism_proposal/proposals.csv")
        primed = [p for p in props if p.get("method") == "primed"]
        if primed and any(p.get("validated") == "True" for p in primed):
            result["status"] = "supported"
            result["evidence_file"] = "neural_morphism_proposal/proposals.csv"
            result["allowed_wording"] = "Neural task-signature priming proposes valid morphisms"
        elif primed:
            result["status"] = "partial"
            result["allowed_wording"] = "Neural priming produces proposals but validation results vary"
        result["forbidden_wording"] = "Neural modules solve cross-domain transfer"

    elif check == "adapter_genesis_compiles":
        sig_csv = read_csv_safe(base / "adapter_signature_compiler/signature_comparison.csv")
        sufficient = [r for r in sig_csv if r.get("sufficient_for_morphism") in ("True", "true")]
        if sufficient:
            result["status"] = "supported" if len(sufficient) >= 2 else "partial"
            result["evidence_file"] = "adapter_signature_compiler/signature_comparison.csv"
            result["allowed_wording"] = (
                f"AdapterGenesis produces signatures sufficient for morphism learning "
                f"in {len(sufficient)}/{len(sig_csv)} domains"
            )
        result["forbidden_wording"] = "AdapterGenesis automatically adapts to arbitrary domains"

    elif check == "transfer_improved":
        existing = read_csv_safe(base / "existing_transfer_as_morphisms.csv")
        micro = read_csv_safe(base / "microcycle/results.csv")
        certifiable = sum(1 for r in existing if r.get("certificate_status") == "certifiable")
        micro_cert = sum(1 for r in micro if r.get("certified") == "True")
        if certifiable > 0 or micro_cert > 0:
            result["status"] = "partial"
            result["evidence_file"] = "existing_transfer_as_morphisms.csv, microcycle/results.csv"
            result["allowed_wording"] = (
                f"Morphism learning adds proof obligations to {certifiable} existing transfers "
                f"and certifies {micro_cert} new pairs"
            )
        result["forbidden_wording"] = "Morphism learning solves cross-domain transfer"

    elif check == "honest_negative":
        result["status"] = "honest_negative"
        result["allowed_wording"] = (
            "Domain-morphism learning is a bounded proof-carrying framework; "
            "broad automatic domain adaptation is not yet proven"
        )
        result["forbidden_wording"] = "Broad automatic domain adaptation is solved"

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="outputs/domain_morphism_learning")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    base = out
    results = [check_claim(c, base) for c in CLAIMS]

    fields = ["claim_id", "claim_text", "status", "evidence_file",
              "allowed_wording", "forbidden_wording"]
    with open(out / "claim_audit.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    status_counts = {}
    for r in results:
        s = r["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    with open(out / "claim_audit.md", "w") as f:
        f.write("# Domain Morphism Claim Audit\n\n")
        f.write("## Summary\n\n")
        for s, c in sorted(status_counts.items()):
            f.write(f"- **{s}**: {c}\n")
        f.write(f"\nTotal claims: {len(results)}\n\n")
        f.write("## Per-Claim Analysis\n\n")
        for r in results:
            f.write(f"### {r['claim_id']}: {r['claim_text']}\n\n")
            f.write(f"- **Status**: {r['status']}\n")
            f.write(f"- **Evidence**: {r['evidence_file'] or 'none'}\n")
            f.write(f"- **Allowed**: {r['allowed_wording']}\n")
            f.write(f"- **Forbidden**: {r['forbidden_wording']}\n\n")

    print(f"Claim audit: {out / 'claim_audit.md'}")
    print(f"CSV: {out / 'claim_audit.csv'}")
    for s, c in sorted(status_counts.items()):
        print(f"  {s}: {c}")


if __name__ == "__main__":
    main()
