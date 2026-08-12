#!/usr/bin/env python3.11
"""Diagnose why AdapterGenesis solved 0 tasks in the deep evaluation."""

import csv
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

OUTPUT_DIR = PROJECT_ROOT / "outputs/deep_project_completion/mechanism_repair_pass/adapter_genesis"

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing deep eval results
    deep_dir = PROJECT_ROOT / "outputs/deep_project_completion/cross_domain_adapter_genesis"

    # Read capability audit
    audit_csv = deep_dir / "capability_audit.csv"
    audit_rows = []
    if audit_csv.exists():
        with open(audit_csv) as f:
            audit_rows = list(csv.DictReader(f))

    # Try to actually run AdapterGenesis on each domain's benchmark tasks
    # to diagnose exactly WHERE the pipeline breaks
    from reasoning_project.adapter_genesis import AdapterGenesis
    from reasoning_project.reasoning_engine import StructuralReasoner, GridDomainAdapter
    from reasoning_project.domain_adapters import GraphDomainAdapter, ChessBoardDomainAdapter, MoleculeGraphDomainAdapter
    from reasoning_project.benchmark_generator import (
        GridTaskGenerator, GraphTaskGenerator, ChessBoardTaskGenerator, MoleculeTaskGenerator
    )

    genesis = AdapterGenesis()

    # Map domains to their generators and hand-coded adapters
    domains = {
        "grid": {
            "generator": GridTaskGenerator(),
            "hand_coded_adapter": GridDomainAdapter(),
            "tasks_fn": ["generate_keep_largest", "generate_keep_smallest"],
        },
        "graph": {
            "generator": GraphTaskGenerator(),
            "hand_coded_adapter": GraphDomainAdapter(),
            "tasks_fn": ["generate_keep_high_degree", "generate_remove_isolated"],
        },
        "chess": {
            "generator": ChessBoardTaskGenerator(),
            "hand_coded_adapter": ChessBoardDomainAdapter(),
            "tasks_fn": ["generate_remove_edge_pieces", "generate_keep_attacked_pieces"],
        },
        "molecule": {
            "generator": MoleculeTaskGenerator(),
            "hand_coded_adapter": MoleculeGraphDomainAdapter(),
            "tasks_fn": ["generate_keep_ring_atoms", "generate_recolor_terminal"],
        },
    }

    failure_categories = [
        "domain_signature_wrong",
        "object_schema_wrong",
        "property_library_missing",
        "relation_algebra_missing",
        "adapter_validation_too_strict",
        "adapter_repair_not_applied",
        "adapter_synthesized_but_not_used",
        "structural_reasoner_not_called",
        "reconstruction_missing",
        "certificate_missing",
        "task_not_adapter_solvable",
    ]

    diagnosis_rows = []

    for domain_name, domain_info in domains.items():
        gen = domain_info["generator"]
        hand_adapter = domain_info["hand_coded_adapter"]

        for task_fn_name in domain_info["tasks_fn"]:
            task_fn = getattr(gen, task_fn_name, None)
            if task_fn is None:
                diagnosis_rows.append({
                    "domain": domain_name,
                    "task": task_fn_name,
                    "failure_category": "task_not_adapter_solvable",
                    "detail": f"Generator method {task_fn_name} not found",
                    "hand_coded_solves": "N/A",
                    "genesis_synthesized": False,
                    "genesis_validation_passed": False,
                    "genesis_solves": False,
                })
                continue

            try:
                task = task_fn()
            except Exception as e:
                diagnosis_rows.append({
                    "domain": domain_name,
                    "task": task_fn_name,
                    "failure_category": "task_not_adapter_solvable",
                    "detail": f"Task generation failed: {e}",
                    "hand_coded_solves": "N/A",
                    "genesis_synthesized": False,
                    "genesis_validation_passed": False,
                    "genesis_solves": False,
                })
                continue

            train_pairs = task.train_pairs
            test_pairs = task.test_pairs

            # Step 1: Does hand-coded adapter solve it?
            hand_solves = False
            try:
                reasoner = StructuralReasoner(hand_adapter)
                test_inputs = [t[0] for t in test_pairs]
                result = reasoner.solve(train_pairs, test_inputs)
                if result:
                    preds, meta = result
                    expected = [t[1] for t in test_pairs]
                    hand_solves = all(
                        hand_adapter.scenes_equal(p, e)
                        for p, e in zip(preds, expected)
                    )
            except Exception as e:
                hand_solves = False

            # Step 2: Does AdapterGenesis synthesize an adapter?
            synthesized = False
            validation_passed = False
            genesis_solves = False
            failure_cat = "unknown"
            detail = ""

            try:
                synth_result = genesis.synthesize(train_pairs, test_pairs)
                if synth_result is None:
                    synthesized = False
                    # Diagnose why synthesis returned None
                    # Try sub-steps manually
                    try:
                        from reasoning_project.adapter_genesis import DomainSignatureExtractor
                        extractor = DomainSignatureExtractor()
                        sig = extractor.extract(train_pairs)
                        if sig is None:
                            failure_cat = "domain_signature_wrong"
                            detail = "DomainSignatureExtractor returned None"
                        else:
                            failure_cat = "object_schema_wrong"
                            detail = f"Synthesis returned None after signature detection (domain={getattr(sig, 'domain_type', 'unknown')})"
                    except Exception as sub_e:
                        failure_cat = "domain_signature_wrong"
                        detail = f"Signature extraction error: {sub_e}"
                else:
                    adapter, validation = synth_result
                    synthesized = True
                    validation_passed = validation.passed

                    if not validation.passed:
                        if not validation.object_extraction_stable:
                            failure_cat = "object_schema_wrong"
                            detail = f"Object extraction unstable: {validation.failure_diagnosis}"
                        elif not validation.reconstruction_valid:
                            failure_cat = "reconstruction_missing"
                            detail = f"Reconstruction failed: {validation.failure_diagnosis}"
                        elif not validation.train_consistency:
                            failure_cat = "property_library_missing"
                            detail = f"Train inconsistency: {validation.failure_diagnosis}"
                        elif not validation.loo_consistency:
                            failure_cat = "adapter_validation_too_strict"
                            detail = f"LOO failed: {validation.failure_diagnosis}"
                        else:
                            failure_cat = "adapter_repair_not_applied"
                            detail = f"Validation failed but no specific cause: {validation.failure_diagnosis}"
                    else:
                        # Adapter synthesized and validated — does it solve?
                        try:
                            reasoner = StructuralReasoner(adapter)
                            test_inputs = [t[0] for t in test_pairs]
                            result = reasoner.solve(train_pairs, test_inputs)
                            if result:
                                preds, meta = result
                                expected = [t[1] for t in test_pairs]
                                genesis_solves = all(
                                    adapter.scenes_equal(p, e)
                                    for p, e in zip(preds, expected)
                                )
                                if genesis_solves:
                                    failure_cat = "none"
                                    detail = f"Solved via {meta.get('strategy', 'unknown')}"
                                else:
                                    failure_cat = "adapter_synthesized_but_not_used"
                                    detail = "Adapter validated but predictions wrong"
                            else:
                                failure_cat = "structural_reasoner_not_called"
                                detail = "Reasoner returned None with synthesized adapter"
                        except Exception as solve_e:
                            failure_cat = "structural_reasoner_not_called"
                            detail = f"Reasoner error: {solve_e}"

            except Exception as e:
                failure_cat = "domain_signature_wrong"
                detail = f"AdapterGenesis.synthesize() exception: {e}"

            diagnosis_rows.append({
                "domain": domain_name,
                "task": task_fn_name,
                "failure_category": failure_cat,
                "detail": detail,
                "hand_coded_solves": str(hand_solves),
                "genesis_synthesized": synthesized,
                "genesis_validation_passed": validation_passed,
                "genesis_solves": genesis_solves,
            })

    # Write CSV
    csv_path = OUTPUT_DIR / "diagnosis.csv"
    with open(csv_path, "w", newline="") as f:
        fields = ["domain", "task", "failure_category", "detail", "hand_coded_solves",
                  "genesis_synthesized", "genesis_validation_passed", "genesis_solves"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(diagnosis_rows)

    # Write markdown summary
    md_path = OUTPUT_DIR / "diagnosis.md"
    with open(md_path, "w") as f:
        f.write(f"# AdapterGenesis Failure Diagnosis\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        # Count by category
        from collections import Counter
        cats = Counter(r["failure_category"] for r in diagnosis_rows)
        f.write("## Failure Category Distribution\n\n")
        f.write("| Category | Count |\n|----------|-------|\n")
        for cat, count in cats.most_common():
            f.write(f"| {cat} | {count} |\n")

        f.write("\n## Per-Task Details\n\n")
        f.write("| Domain | Task | Hand-coded Solves | Synthesized | Validated | Genesis Solves | Failure | Detail |\n")
        f.write("|--------|------|-------------------|-------------|-----------|----------------|---------|--------|\n")
        for r in diagnosis_rows:
            f.write(f"| {r['domain']} | {r['task']} | {r['hand_coded_solves']} | "
                    f"{r['genesis_synthesized']} | {r['genesis_validation_passed']} | "
                    f"{r['genesis_solves']} | {r['failure_category']} | {r['detail'][:80]} |\n")

        f.write("\n## Recommended Patches\n\n")
        if "domain_signature_wrong" in cats:
            f.write("- **Domain signature**: Check DomainSignatureExtractor handles all input formats\n")
        if "object_schema_wrong" in cats:
            f.write("- **Object schema**: Ensure ObjectSchemaProposer produces extractable objects for each domain\n")
        if "property_library_missing" in cats:
            f.write("- **Property library**: Add minimal universal properties to PropertyLibraryProposer\n")
        if "structural_reasoner_not_called" in cats:
            f.write("- **Reasoner integration**: Ensure synthesized adapter is passed to StructuralReasoner\n")
        if "adapter_synthesized_but_not_used" in cats:
            f.write("- **Prediction path**: Synthesized adapter passes validation but doesn't produce correct output\n")
        if "adapter_repair_not_applied" in cats:
            f.write("- **Repair loop**: Ensure AdapterRepairer is invoked on failed validations\n")

    print(f"Diagnosis written to {md_path}")
    print(f"CSV written to {csv_path}")
    print(f"Total tasks diagnosed: {len(diagnosis_rows)}")
    for cat, count in cats.most_common():
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
