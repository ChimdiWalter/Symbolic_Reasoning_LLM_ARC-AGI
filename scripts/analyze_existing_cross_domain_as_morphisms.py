#!/usr/bin/env python3.11
"""Phase 5: Reinterpret existing cross-domain transfers as morphisms."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from reasoning_project.cross_domain_operator_semantics import OperatorFamilyName
from reasoning_project.abstract_operator_schemas import SCHEMA_BY_FAMILY
from reasoning_project.domain_morphism import (
    DomainSignatureExtractorTyped, DomainMorphismLearner,
)
from reasoning_project.reasoning_engine import GridDomainAdapter
from reasoning_project.domain_adapters import (
    GraphDomainAdapter, ChessBoardDomainAdapter, MoleculeGraphDomainAdapter,
)
from reasoning_project.morphism_verification import MorphismProofObligations

PROJECT_ROOT = Path("/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project")

FAMILY_MAP = {
    "PROJECT_TO_NEIGHBORHOOD": OperatorFamilyName.PROJECT_TO_NEIGHBORHOOD,
    "COPY_FEATURE_TO_CORRESPONDENT": OperatorFamilyName.COPY_FEATURE_TO_CORRESPONDENT,
    "FILTER_BY_RELATION": OperatorFamilyName.FILTER_BY_RELATION,
    "MOVE_OR_TRANSFER_TO_ANCHOR": OperatorFamilyName.MOVE_OR_TRANSFER_TO_ANCHOR,
}

ADAPTER_MAP = {
    "grid": GridDomainAdapter,
    "graph": GraphDomainAdapter,
    "chess": ChessBoardDomainAdapter,
    "molecule": MoleculeGraphDomainAdapter,
}


def read_csv_safe(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def read_text_safe(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="outputs/domain_morphism_learning")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    transfer_results = read_csv_safe(
        PROJECT_ROOT / "outputs/deep_project_completion/cross_domain_operator_transfer/results.csv"
    )
    repair_results = read_csv_safe(
        PROJECT_ROOT / "outputs/deep_project_completion/mechanism_repair_pass/cross_domain_transfer/transfer_matrix.csv"
    )
    aligned_summary = read_text_safe(
        PROJECT_ROOT / "outputs/deep_project_completion/mechanism_repair_pass/cross_domain_transfer/aligned_microcycle_summary.md"
    )

    all_transfers = transfer_results + repair_results

    extractor = DomainSignatureExtractorTyped()
    learner = DomainMorphismLearner()
    checker = MorphismProofObligations()

    sig_cache: Dict[str, Any] = {}
    for dname, adapter_cls in ADAPTER_MAP.items():
        sig_cache[dname] = extractor.extract(adapter_cls())

    rows: List[Dict[str, Any]] = []

    for tr in all_transfers:
        src = tr.get("source", tr.get("source_domain", "")).strip().lower()
        tgt = tr.get("target", tr.get("target_domain", "")).strip().lower()
        family_str = tr.get("family", tr.get("operator_family", "")).strip()
        solved = tr.get("solved", tr.get("tasks_solved", "0"))
        zero_shot = tr.get("zero_shot", "False")

        family_enum = FAMILY_MAP.get(family_str)
        schema = SCHEMA_BY_FAMILY.get(family_enum) if family_enum else None

        row: Dict[str, Any] = {
            "source_domain": src,
            "target_domain": tgt,
            "operator_family": family_str,
            "abstract_schema": schema.name if schema else "unknown",
            "inferred_morphism_quality": "N/A",
            "obligations_satisfied": 0,
            "obligations_missing": 0,
            "certificate_status": "not_checked",
        }

        if src in sig_cache and tgt in sig_cache:
            src_sig = sig_cache[src]
            tgt_sig = sig_cache[tgt]
            morphisms = learner.propose_morphisms(src_sig, tgt_sig)
            morphisms = learner.reject_ambiguous(morphisms)

            if morphisms:
                best = max(morphisms, key=lambda m: m.score)
                row["inferred_morphism_quality"] = f"{best.score:.3f}"

                obligations = checker.check_all(best, src_sig, tgt_sig, schema)
                sat = sum(1 for o in obligations if o.passed)
                total = len(obligations)
                row["obligations_satisfied"] = sat
                row["obligations_missing"] = total - sat

                if sat == total and str(solved) not in ("0", "False", ""):
                    row["certificate_status"] = "certifiable"
                elif sat == total:
                    row["certificate_status"] = "morphism_valid_but_no_solve"
                else:
                    failed = [o.name for o in obligations if not o.passed]
                    row["certificate_status"] = f"obligations_failed:{','.join(failed)}"
            else:
                row["certificate_status"] = "morphisms_rejected"
        else:
            row["certificate_status"] = "unknown_domain"

        rows.append(row)

    if not all_transfers:
        rows.append({
            "source_domain": "N/A", "target_domain": "N/A",
            "operator_family": "N/A", "abstract_schema": "N/A",
            "inferred_morphism_quality": "N/A",
            "obligations_satisfied": 0, "obligations_missing": 0,
            "certificate_status": "no_prior_transfers_found",
        })

    fields = ["source_domain", "target_domain", "operator_family", "abstract_schema",
              "inferred_morphism_quality", "obligations_satisfied", "obligations_missing",
              "certificate_status"]
    with open(out / "existing_transfer_as_morphisms.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    with open(out / "existing_transfer_reinterpretation.md", "w") as f:
        f.write("# Existing Cross-Domain Transfers Reinterpreted as Morphisms\n\n")
        f.write(f"Prior transfers analyzed: {len(all_transfers)}\n\n")

        certifiable = sum(1 for r in rows if r["certificate_status"] == "certifiable")
        valid_no_solve = sum(1 for r in rows if r["certificate_status"] == "morphism_valid_but_no_solve")
        failed = sum(1 for r in rows if "obligations_failed" in str(r["certificate_status"]))

        f.write(f"- **Certifiable** (morphism valid + task solved): {certifiable}\n")
        f.write(f"- **Morphism valid but no solve**: {valid_no_solve}\n")
        f.write(f"- **Obligations failed**: {failed}\n")
        f.write(f"- **Other**: {len(rows) - certifiable - valid_no_solve - failed}\n\n")

        f.write("## Per-Transfer Analysis\n\n")
        f.write("| Source | Target | Family | Schema | Morphism Score | Obligations | Status |\n")
        f.write("|--------|--------|--------|--------|---------------|-------------|--------|\n")
        for r in rows:
            sat = r["obligations_satisfied"]
            total = sat + r["obligations_missing"]
            f.write(f"| {r['source_domain']} | {r['target_domain']} | {r['operator_family']} "
                    f"| {r['abstract_schema']} | {r['inferred_morphism_quality']} "
                    f"| {sat}/{total} | {r['certificate_status']} |\n")

        if aligned_summary:
            f.write("\n## Prior Aligned Microcycle Summary\n\n")
            f.write(aligned_summary[:2000])

    print(f"CSV: {out / 'existing_transfer_as_morphisms.csv'}")
    print(f"Report: {out / 'existing_transfer_reinterpretation.md'}")
    print(f"Transfers analyzed: {len(all_transfers)}")
    print(f"Certifiable: {certifiable}, Valid no solve: {valid_no_solve}, Failed: {failed}")


if __name__ == "__main__":
    main()
