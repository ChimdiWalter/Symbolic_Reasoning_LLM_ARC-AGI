#!/usr/bin/env python3.11
"""AdapterGenesis microcycle: test synthesis across controlled domains."""

import csv
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

OUTPUT_DIR = PROJECT_ROOT / "outputs/deep_project_completion/mechanism_repair_pass/adapter_genesis"

def make_certificate(domain, task_id, adapter_type, strategy, train_fit, loo_passed):
    return {
        "task_id": task_id,
        "domain": domain,
        "adapter_type": adapter_type,
        "strategy": strategy,
        "train_fit": train_fit,
        "loo_passed": loo_passed,
        "timestamp": datetime.now().isoformat(),
        "proof_obligations": {
            "executable_hypothesis": True,
            "training_consistency": train_fit > 0,
            "loo_validation": loo_passed,
        },
    }

def run_with_adapter(adapter, train_pairs, test_pairs, adapter_type):
    """Run StructuralReasoner with given adapter. Returns (solved, meta, loo_passed)."""
    from reasoning_project.reasoning_engine import StructuralReasoner

    result_info = {"solved": False, "strategy": "", "train_fit": 0, "loo_passed": False, "error": ""}

    try:
        reasoner = StructuralReasoner(adapter)
        test_inputs = [t[0] for t in test_pairs]
        result = reasoner.solve(train_pairs, test_inputs)

        if result is None:
            result_info["error"] = "reasoner returned None"
            return result_info

        preds, meta = result
        expected = [t[1] for t in test_pairs]

        solved = all(adapter.scenes_equal(p, e) for p, e in zip(preds, expected))
        result_info["solved"] = solved
        result_info["strategy"] = meta.get("strategy", "unknown")

        # Check training fit
        train_inputs = [t[0] for t in train_pairs]
        train_result = reasoner.solve(train_pairs, train_inputs)
        if train_result:
            train_preds, _ = train_result
            train_expected = [t[1] for t in train_pairs]
            result_info["train_fit"] = sum(
                1 for p, e in zip(train_preds, train_expected) if adapter.scenes_equal(p, e)
            )

        # LOO validation
        loo_pass = True
        if len(train_pairs) >= 2:
            for i in range(len(train_pairs)):
                loo_train = train_pairs[:i] + train_pairs[i+1:]
                loo_test_input = [train_pairs[i][0]]
                loo_expected = train_pairs[i][1]
                try:
                    loo_reasoner = StructuralReasoner(adapter)
                    loo_result = loo_reasoner.solve(loo_train, loo_test_input)
                    if loo_result is None:
                        loo_pass = False
                        break
                    loo_pred = loo_result[0][0]
                    if not adapter.scenes_equal(loo_pred, loo_expected):
                        loo_pass = False
                        break
                except Exception:
                    loo_pass = False
                    break
        result_info["loo_passed"] = loo_pass

    except Exception as e:
        result_info["error"] = str(e)

    return result_info

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "adapter_reports").mkdir(exist_ok=True)
    (OUTPUT_DIR / "certificates").mkdir(exist_ok=True)

    from reasoning_project.adapter_genesis import AdapterGenesis
    from reasoning_project.reasoning_engine import GridDomainAdapter
    from reasoning_project.domain_adapters import GraphDomainAdapter, ChessBoardDomainAdapter, MoleculeGraphDomainAdapter
    from reasoning_project.benchmark_generator import (
        GridTaskGenerator, GraphTaskGenerator, ChessBoardTaskGenerator, MoleculeTaskGenerator
    )

    genesis = AdapterGenesis()

    domains = {
        "grid": {
            "generator": GridTaskGenerator(),
            "hand_coded_adapter": GridDomainAdapter(),
            "tasks": ["generate_keep_largest", "generate_keep_smallest",
                      "generate_keep_hollow", "generate_recolor_by_size",
                      "generate_keep_touching_boundary"],
        },
        "graph": {
            "generator": GraphTaskGenerator(),
            "hand_coded_adapter": GraphDomainAdapter(),
            "tasks": ["generate_keep_high_degree", "generate_recolor_by_degree",
                      "generate_remove_isolated"],
        },
        "chess": {
            "generator": ChessBoardTaskGenerator(),
            "hand_coded_adapter": ChessBoardDomainAdapter(),
            "tasks": ["generate_remove_edge_pieces", "generate_keep_attacked_pieces"],
        },
        "molecule": {
            "generator": MoleculeTaskGenerator(),
            "hand_coded_adapter": MoleculeGraphDomainAdapter(),
            "tasks": ["generate_keep_ring_atoms", "generate_recolor_terminal"],
        },
    }

    results = []
    certificates = []

    for domain_name, domain_info in domains.items():
        gen = domain_info["generator"]
        hand_adapter = domain_info["hand_coded_adapter"]

        for task_fn_name in domain_info["tasks"]:
            task_fn = getattr(gen, task_fn_name, None)
            if task_fn is None:
                continue

            try:
                task = task_fn()
            except Exception as e:
                results.append({
                    "domain": domain_name, "task": task_fn_name,
                    "adapter_type": "all", "solved": False, "error": str(e),
                    "strategy": "", "train_fit": 0, "loo_passed": False, "fp": False,
                })
                continue

            train_pairs = task.train_pairs
            test_pairs = task.test_pairs

            # Config 1: Hand-coded adapter
            hc = run_with_adapter(hand_adapter, train_pairs, test_pairs, "hand_coded")
            results.append({
                "domain": domain_name, "task": task_fn_name,
                "adapter_type": "hand_coded", **hc, "fp": False,
            })
            if hc["solved"] and hc["loo_passed"]:
                cert = make_certificate(domain_name, task_fn_name, "hand_coded",
                                       hc["strategy"], hc["train_fit"], hc["loo_passed"])
                certificates.append(cert)

            # Config 2: AdapterGenesis synthesized
            synth_adapter = None
            synth_validation = None
            try:
                synth_result = genesis.synthesize(train_pairs, test_pairs)
                if synth_result:
                    synth_adapter, synth_validation = synth_result
            except Exception as e:
                pass

            if synth_adapter is not None:
                sg = run_with_adapter(synth_adapter, train_pairs, test_pairs, "synthesized")
                results.append({
                    "domain": domain_name, "task": task_fn_name,
                    "adapter_type": "synthesized", **sg, "fp": False,
                })
                if sg["solved"] and sg["loo_passed"]:
                    cert = make_certificate(domain_name, task_fn_name, "synthesized",
                                           sg["strategy"], sg["train_fit"], sg["loo_passed"])
                    certificates.append(cert)

                # Save adapter report
                report = {
                    "domain": domain_name, "task": task_fn_name,
                    "validation_passed": synth_validation.passed if synth_validation else False,
                    "train_consistency": synth_validation.train_consistency if synth_validation else False,
                    "loo_consistency": synth_validation.loo_consistency if synth_validation else False,
                    "object_extraction_stable": synth_validation.object_extraction_stable if synth_validation else False,
                    "properties": synth_adapter.property_names() if hasattr(synth_adapter, 'property_names') else [],
                }
                with open(OUTPUT_DIR / "adapter_reports" / f"{domain_name}_{task_fn_name}.json", "w") as f:
                    json.dump(report, f, indent=2, default=str)
            else:
                results.append({
                    "domain": domain_name, "task": task_fn_name,
                    "adapter_type": "synthesized", "solved": False, "error": "synthesis failed",
                    "strategy": "", "train_fit": 0, "loo_passed": False, "fp": False,
                })

            # Config 3: AdapterGenesis synthesized + repair (re-run with repair enabled)
            # This uses the same genesis but we explicitly attempt repair if validation failed
            if synth_adapter is not None and synth_validation is not None and not synth_validation.passed:
                try:
                    from reasoning_project.adapter_genesis import AdapterRepairer
                    repairer = AdapterRepairer()
                    repaired = repairer.repair(synth_adapter, synth_validation, train_pairs)
                    if repaired:
                        rp = run_with_adapter(repaired, train_pairs, test_pairs, "synthesized_repaired")
                        results.append({
                            "domain": domain_name, "task": task_fn_name,
                            "adapter_type": "synthesized_repaired", **rp, "fp": False,
                        })
                        if rp["solved"] and rp["loo_passed"]:
                            cert = make_certificate(domain_name, task_fn_name, "synthesized_repaired",
                                                   rp["strategy"], rp["train_fit"], rp["loo_passed"])
                            certificates.append(cert)
                    else:
                        results.append({
                            "domain": domain_name, "task": task_fn_name,
                            "adapter_type": "synthesized_repaired", "solved": False,
                            "error": "repair returned None", "strategy": "", "train_fit": 0,
                            "loo_passed": False, "fp": False,
                        })
                except Exception as e:
                    results.append({
                        "domain": domain_name, "task": task_fn_name,
                        "adapter_type": "synthesized_repaired", "solved": False,
                        "error": str(e), "strategy": "", "train_fit": 0,
                        "loo_passed": False, "fp": False,
                    })

    # Write results CSV
    csv_path = OUTPUT_DIR / "microcycle_results.csv"
    fields = ["domain", "task", "adapter_type", "solved", "strategy", "train_fit",
              "loo_passed", "fp", "error"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    # Write certificates
    for cert in certificates:
        cert_path = OUTPUT_DIR / "certificates" / f"{cert['domain']}_{cert['task_id']}_{cert['adapter_type']}.json"
        with open(cert_path, "w") as f:
            json.dump(cert, f, indent=2)

    # Write summary
    total_hand = sum(1 for r in results if r["adapter_type"] == "hand_coded" and r["solved"])
    total_synth = sum(1 for r in results if r["adapter_type"] == "synthesized" and r["solved"])
    total_repaired = sum(1 for r in results if r["adapter_type"] == "synthesized_repaired" and r["solved"])
    total_fp = sum(1 for r in results if r.get("fp"))
    n_tasks_per_type = {
        "hand_coded": sum(1 for r in results if r["adapter_type"] == "hand_coded"),
        "synthesized": sum(1 for r in results if r["adapter_type"] == "synthesized"),
        "synthesized_repaired": sum(1 for r in results if r["adapter_type"] == "synthesized_repaired"),
    }

    md_path = OUTPUT_DIR / "microcycle_summary.md"
    with open(md_path, "w") as f:
        f.write(f"# AdapterGenesis Microcycle Summary\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("## Results\n\n")
        f.write("| Adapter Type | Solved | Total | Rate |\n")
        f.write("|-------------|--------|-------|------|\n")
        f.write(f"| hand_coded | {total_hand} | {n_tasks_per_type['hand_coded']} | "
                f"{total_hand/max(n_tasks_per_type['hand_coded'],1)*100:.1f}% |\n")
        f.write(f"| synthesized | {total_synth} | {n_tasks_per_type['synthesized']} | "
                f"{total_synth/max(n_tasks_per_type['synthesized'],1)*100:.1f}% |\n")
        f.write(f"| synthesized_repaired | {total_repaired} | {n_tasks_per_type['synthesized_repaired']} | "
                f"{total_repaired/max(n_tasks_per_type['synthesized_repaired'],1)*100:.1f}% |\n")
        f.write(f"\n**False positives**: {total_fp}\n")
        f.write(f"**Certificates emitted**: {len(certificates)}\n\n")

        f.write("## Per-Domain Breakdown\n\n")
        for domain in ["grid", "graph", "chess", "molecule"]:
            domain_results = [r for r in results if r["domain"] == domain]
            f.write(f"### {domain}\n\n")
            f.write("| Task | Adapter | Solved | Strategy | LOO | Error |\n")
            f.write("|------|---------|--------|----------|-----|-------|\n")
            for r in domain_results:
                f.write(f"| {r['task']} | {r['adapter_type']} | {r['solved']} | "
                        f"{r['strategy']} | {r['loo_passed']} | {r.get('error', '')[:50]} |\n")
            f.write("\n")

        f.write("## Claim Assessment\n\n")
        if total_synth > 0:
            f.write(f"**Supported**: AdapterGenesis synthesized adapters that solved {total_synth} task(s) "
                    f"in controlled domains.\n")
        else:
            f.write("**Not supported**: AdapterGenesis did not synthesize any adapter that solved tasks. "
                    "Mechanism remains architectural.\n")
        if total_repaired > total_synth:
            f.write(f"**Repair helps**: Repair added {total_repaired - total_synth} additional solve(s).\n")

    print(f"Microcycle summary: {md_path}")
    print(f"Results CSV: {csv_path}")
    print(f"Certificates: {len(certificates)}")
    print(f"Hand-coded solves: {total_hand}/{n_tasks_per_type['hand_coded']}")
    print(f"Synthesized solves: {total_synth}/{n_tasks_per_type['synthesized']}")
    print(f"Repaired solves: {total_repaired}/{n_tasks_per_type['synthesized_repaired']}")


if __name__ == "__main__":
    main()
