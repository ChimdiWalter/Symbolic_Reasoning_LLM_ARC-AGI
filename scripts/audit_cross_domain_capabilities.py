#!/usr/bin/env python3
"""Phase B: Audit cross-domain capabilities.

Checks what domain adapters, AdapterGenesis, and StructuralReasoner
support across grid, graph, chess, molecule, conceptarc domains.
"""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def audit_domain(domain_name, adapter_cls, genesis_available, generator_cls):
    result = {
        "domain": domain_name,
        "hand_coded_adapter": False,
        "adapter_functional": False,
        "adapter_genesis_synthesis": False,
        "adapter_genesis_repair": False,
        "object_schema": "none",
        "property_library": "none",
        "relation_algebra": "none",
        "operator_families": "",
        "generator_available": generator_cls is not None,
        "notes": "",
    }

    if adapter_cls is not None:
        result["hand_coded_adapter"] = True
        try:
            adapter = adapter_cls()
            result["adapter_functional"] = True
            if hasattr(adapter, "property_names"):
                props = adapter.property_names()
                result["property_library"] = f"{len(props)} properties"
            if hasattr(adapter, "extract_objects"):
                result["object_schema"] = "extract_objects implemented"
            if hasattr(adapter, "reconstruct_filtered"):
                result["relation_algebra"] = "reconstruct_filtered implemented"
        except Exception as e:
            result["notes"] = f"adapter init error: {e}"

    if genesis_available:
        try:
            from reasoning_project.adapter_genesis import AdapterGenesis
            ag = AdapterGenesis()
            result["adapter_genesis_synthesis"] = hasattr(ag, "synthesize")
            result["adapter_genesis_repair"] = hasattr(ag, "synthesize_and_solve")
        except Exception as e:
            result["notes"] += f"; genesis error: {e}"

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="outputs/deep_project_completion/cross_domain_adapter_genesis")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== Cross-Domain Capability Audit ===")

    domains = []

    # Grid
    try:
        from reasoning_project.reasoning_engine import GridDomainAdapter
        grid_adapter = GridDomainAdapter
    except ImportError:
        grid_adapter = None
    try:
        from reasoning_project.benchmark_generator import GridTaskGenerator
        grid_gen = GridTaskGenerator
    except ImportError:
        grid_gen = None
    domains.append(audit_domain("grid", grid_adapter, True, grid_gen))

    # Graph
    try:
        from reasoning_project.domain_adapters import GraphDomainAdapter
        graph_adapter = GraphDomainAdapter
    except ImportError:
        graph_adapter = None
    try:
        from reasoning_project.benchmark_generator import GraphTaskGenerator
        graph_gen = GraphTaskGenerator
    except ImportError:
        graph_gen = None
    domains.append(audit_domain("graph", graph_adapter, True, graph_gen))

    # Chess
    try:
        from reasoning_project.domain_adapters import ChessBoardDomainAdapter
        chess_adapter = ChessBoardDomainAdapter
    except ImportError:
        chess_adapter = None
    try:
        from reasoning_project.benchmark_generator import ChessBoardTaskGenerator
        chess_gen = ChessBoardTaskGenerator
    except ImportError:
        chess_gen = None
    domains.append(audit_domain("chess", chess_adapter, True, chess_gen))

    # Molecule
    try:
        from reasoning_project.domain_adapters import MoleculeGraphDomainAdapter
        mol_adapter = MoleculeGraphDomainAdapter
    except ImportError:
        mol_adapter = None
    try:
        from reasoning_project.benchmark_generator import MoleculeTaskGenerator
        mol_gen = MoleculeTaskGenerator
    except ImportError:
        mol_gen = None
    domains.append(audit_domain("molecule", mol_adapter, True, mol_gen))

    # ConceptARC (uses grid adapter)
    domains.append(audit_domain("conceptarc", grid_adapter, True, None))

    # Write CSV
    with open(output_dir / "capability_audit.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(domains[0].keys()))
        writer.writeheader()
        for d in domains:
            writer.writerow(d)

    # Write markdown
    lines = ["# Cross-Domain Capability Audit", f"\nGenerated: {datetime.now().isoformat()}", ""]
    lines.append("| Domain | Hand-coded | Functional | Genesis | Generator | Properties |")
    lines.append("|--------|-----------|-----------|---------|-----------|------------|")
    for d in domains:
        lines.append(f"| {d['domain']} | {d['hand_coded_adapter']} | {d['adapter_functional']} | {d['adapter_genesis_synthesis']} | {d['generator_available']} | {d['property_library']} |")

    with open(output_dir / "capability_audit.md", "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Written to {output_dir}/")
    for d in domains:
        print(f"  {d['domain']}: adapter={d['adapter_functional']}, genesis={d['adapter_genesis_synthesis']}, gen={d['generator_available']}")


if __name__ == "__main__":
    main()
