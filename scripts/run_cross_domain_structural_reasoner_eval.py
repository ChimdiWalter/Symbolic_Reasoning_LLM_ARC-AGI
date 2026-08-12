#!/usr/bin/env python3
"""Phase B: Cross-domain StructuralReasoner evaluation."""
import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="outputs/deep_project_completion/cross_domain_adapter_genesis")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== Cross-Domain StructuralReasoner Eval ===")
    results = []

    domains = [
        ("grid", "reasoning_project.reasoning_engine", "GridDomainAdapter", "reasoning_project.benchmark_generator", "GridTaskGenerator"),
        ("graph", "reasoning_project.domain_adapters", "GraphDomainAdapter", "reasoning_project.benchmark_generator", "GraphTaskGenerator"),
        ("chess", "reasoning_project.domain_adapters", "ChessBoardDomainAdapter", "reasoning_project.benchmark_generator", "ChessBoardTaskGenerator"),
        ("molecule", "reasoning_project.domain_adapters", "MoleculeGraphDomainAdapter", "reasoning_project.benchmark_generator", "MoleculeTaskGenerator"),
    ]

    for domain, adapter_mod, adapter_cls_name, gen_mod, gen_cls_name in domains:
        try:
            import importlib
            a_mod = importlib.import_module(adapter_mod)
            adapter_cls = getattr(a_mod, adapter_cls_name)
            g_mod = importlib.import_module(gen_mod)
            gen_cls = getattr(g_mod, gen_cls_name)

            from reasoning_project.reasoning_engine import StructuralReasoner
            adapter = adapter_cls()
            reasoner = StructuralReasoner(adapter)
            gen = gen_cls(seed=42)
            tasks = gen.generate(n_tasks=20)

            for i, task in enumerate(tasks):
                t0 = time.time()
                try:
                    train_pairs = [(ex["input"], ex["output"]) for ex in task["train"]]
                    test_inputs = [ex["input"] for ex in task["test"]]
                    preds, meta = reasoner.solve(train_pairs, test_inputs)
                    solved = preds is not None and meta.get("training_fit", 0) >= len(train_pairs)
                    results.append({
                        "domain": domain,
                        "task_idx": i,
                        "solved": solved,
                        "solver": meta.get("solver", ""),
                        "phase_reached": meta.get("phase", ""),
                        "runtime": round(time.time() - t0, 2),
                    })
                except Exception as e:
                    results.append({
                        "domain": domain,
                        "task_idx": i,
                        "solved": False,
                        "solver": "",
                        "phase_reached": f"error:{type(e).__name__}",
                        "runtime": round(time.time() - t0, 2),
                    })
            solved_count = sum(1 for r in results if r["domain"] == domain and r["solved"])
            print(f"  {domain}: {solved_count}/20 solved")
        except Exception as e:
            print(f"  {domain}: error — {e}")

    if results:
        with open(output_dir / "structural_reasoner_cross_domain.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            for r in results:
                writer.writerow(r)

    print(f"Written to {output_dir}/")


if __name__ == "__main__":
    main()
