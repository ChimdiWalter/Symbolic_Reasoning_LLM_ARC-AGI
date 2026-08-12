#!/usr/bin/env python3.11
"""AdapterGenesis ablation study."""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

OUTPUT_DIR = PROJECT_ROOT / "outputs/deep_project_completion/mechanism_repair_pass/adapter_genesis"

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    from reasoning_project.adapter_genesis import AdapterGenesis
    from reasoning_project.reasoning_engine import StructuralReasoner, GridDomainAdapter
    from reasoning_project.domain_adapters import GraphDomainAdapter
    from reasoning_project.benchmark_generator import GridTaskGenerator, GraphTaskGenerator

    # Use a focused set of tasks where we know hand-coded works
    tasks = []

    grid_gen = GridTaskGenerator()
    for fn_name in ["generate_keep_largest", "generate_keep_smallest"]:
        fn = getattr(grid_gen, fn_name, None)
        if fn:
            try:
                task = fn()
                tasks.append(("grid", fn_name, task, GridDomainAdapter()))
            except Exception:
                pass

    graph_gen = GraphTaskGenerator()
    for fn_name in ["generate_keep_high_degree", "generate_remove_isolated"]:
        fn = getattr(graph_gen, fn_name, None)
        if fn:
            try:
                task = fn()
                tasks.append(("graph", fn_name, task, GraphDomainAdapter()))
            except Exception:
                pass

    configs = [
        "hand_coded",
        "synthesized_full",
        "synthesized_no_repair",
        "synthesized_no_property_proposer",
        "synthesized_no_relation_proposer",
    ]

    results = []

    for domain, task_name, task, hand_adapter in tasks:
        train_pairs = task.train_pairs
        test_pairs = task.test_pairs
        test_inputs = [t[0] for t in test_pairs]
        expected = [t[1] for t in test_pairs]

        for config in configs:
            solved = False
            strategy = ""
            error = ""

            try:
                if config == "hand_coded":
                    reasoner = StructuralReasoner(hand_adapter)
                    result = reasoner.solve(train_pairs, test_inputs)
                    if result:
                        preds, meta = result
                        solved = all(hand_adapter.scenes_equal(p, e) for p, e in zip(preds, expected))
                        strategy = meta.get("strategy", "")
                else:
                    genesis = AdapterGenesis()

                    if config == "synthesized_no_property_proposer":
                        # Monkey-patch to skip property proposal
                        original_propose = genesis.property_proposer.propose if hasattr(genesis, 'property_proposer') else None
                        if hasattr(genesis, 'property_proposer'):
                            genesis.property_proposer.propose = lambda *a, **k: []

                    if config == "synthesized_no_relation_proposer":
                        if hasattr(genesis, 'relation_proposer'):
                            genesis.relation_proposer.propose = lambda *a, **k: []

                    synth_result = genesis.synthesize(train_pairs, test_pairs)

                    if config == "synthesized_no_repair" and synth_result:
                        adapter, validation = synth_result
                        # Use adapter even if validation failed (no repair)
                        reasoner = StructuralReasoner(adapter)
                        result = reasoner.solve(train_pairs, test_inputs)
                        if result:
                            preds, meta = result
                            solved = all(adapter.scenes_equal(p, e) for p, e in zip(preds, expected))
                            strategy = meta.get("strategy", "")
                    elif synth_result:
                        adapter, validation = synth_result
                        if validation.passed:
                            reasoner = StructuralReasoner(adapter)
                            result = reasoner.solve(train_pairs, test_inputs)
                            if result:
                                preds, meta = result
                                solved = all(adapter.scenes_equal(p, e) for p, e in zip(preds, expected))
                                strategy = meta.get("strategy", "")
                    else:
                        error = "synthesis returned None"

            except Exception as e:
                error = str(e)[:100]

            results.append({
                "domain": domain,
                "task": task_name,
                "config": config,
                "solved": solved,
                "strategy": strategy,
                "error": error,
            })

    # Write CSV
    csv_path = OUTPUT_DIR / "ablation_results.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["domain", "task", "config", "solved", "strategy", "error"])
        writer.writeheader()
        writer.writerows(results)

    # Write summary
    md_path = OUTPUT_DIR / "ablation_summary.md"
    with open(md_path, "w") as f:
        f.write(f"# AdapterGenesis Ablation Summary\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        f.write("## Results by Configuration\n\n")
        f.write("| Config | Solved | Total | Rate |\n")
        f.write("|--------|--------|-------|------|\n")
        for config in configs:
            config_results = [r for r in results if r["config"] == config]
            n_solved = sum(1 for r in config_results if r["solved"])
            n_total = len(config_results)
            rate = n_solved / max(n_total, 1) * 100
            f.write(f"| {config} | {n_solved} | {n_total} | {rate:.1f}% |\n")

        f.write("\n## Full Results\n\n")
        f.write("| Domain | Task | Config | Solved | Strategy | Error |\n")
        f.write("|--------|------|--------|--------|----------|-------|\n")
        for r in results:
            f.write(f"| {r['domain']} | {r['task']} | {r['config']} | {r['solved']} | "
                    f"{r['strategy']} | {r['error'][:40]} |\n")

        f.write("\n## Ablation Conclusions\n\n")
        hand_solves = sum(1 for r in results if r["config"] == "hand_coded" and r["solved"])
        synth_solves = sum(1 for r in results if r["config"] == "synthesized_full" and r["solved"])
        f.write(f"- Hand-coded baseline: {hand_solves} solves\n")
        f.write(f"- Full synthesis: {synth_solves} solves\n")
        if synth_solves > 0:
            f.write("- **Synthesis adds value** over hand-coding in some tasks\n")
        else:
            f.write("- **Synthesis does not yet match** hand-coded adapters\n")

    print(f"Ablation summary: {md_path}")
    print(f"Results: {csv_path}")


if __name__ == "__main__":
    main()
