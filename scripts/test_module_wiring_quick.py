"""Quick local test: do the newly wired modules produce executable proposals?

Tests a few previously-unsolved tasks to check if neural_advisory,
manifold_memory, adapter_genesis, or property_expansion now generate
executable proposals that pass the verifier.
"""
from __future__ import annotations
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from reasoning_project.adaptive_orchestrator import (
    GatedAdaptiveReasoningOrchestrator,
    OrchestratorConfig,
)
from reasoning_project.arc_adapter import load_arc_tasks

ARC_ROOT = Path(__file__).parent.parent / "data" / "arc"

UNSOLVED_SAMPLE = [
    "137eaa0f", "05f2a901", "137f0df0", "0607ce86", "0becf7df",
    "06df4c85", "0e206a2e", "14754a24", "017c7c7b", "0962bcdd",
]


def main():
    arc_tasks = load_arc_tasks(ARC_ROOT)
    task_map = {t.task_id: t for t in arc_tasks}

    config = OrchestratorConfig(timeout_per_task=300.0)
    orchestrator = GatedAdaptiveReasoningOrchestrator(config=config)

    new_module_solves = {}
    module_proposal_counts = {}

    for task_id in UNSOLVED_SAMPLE:
        task = task_map.get(task_id)
        if task is None:
            print(f"  SKIP {task_id}: not found in ARC data")
            continue

        train_pairs = [(p.input_grid, p.output_grid) for p in task.train]
        test_inputs = [p.input_grid for p in task.test]

        t0 = time.time()
        trace = orchestrator.solve_task(
            task_id, train_pairs, test_inputs, domain="arc"
        )
        elapsed = time.time() - t0

        for p in trace.proposals:
            module_proposal_counts[p.module_name] = module_proposal_counts.get(p.module_name, 0) + 1
            hyp = p.hypothesis
            has_exec = (callable(hyp) or
                        (isinstance(hyp, dict) and callable(hyp.get("execute"))))
            exec_tag = "EXEC" if has_exec else "meta"
            if has_exec and p.module_name not in ("static_portfolio", "frontier_operators", "trace_invention"):
                print(f"  NEW EXEC from {p.module_name}: family={p.operator_family}, "
                      f"conf={p.confidence:.2f}")

        status_tag = "SOLVED" if trace.final_status == "solved" else trace.final_status
        module_tag = ""
        if trace.selected_proposal:
            module_tag = f" by {trace.selected_proposal.module_name}"
            if trace.selected_proposal.module_name not in ("static_portfolio", "frontier_operators"):
                new_module_solves[task_id] = trace.selected_proposal.module_name

        print(f"  [{task_id}] {status_tag}{module_tag} "
              f"({len(trace.proposals)} proposals, {elapsed:.1f}s)")

    print(f"\n=== Summary ===")
    print(f"Proposal counts by module:")
    for mod, count in sorted(module_proposal_counts.items(), key=lambda x: -x[1]):
        print(f"  {mod}: {count}")
    print(f"\nNew module solves: {len(new_module_solves)}")
    for tid, mod in new_module_solves.items():
        print(f"  {tid} solved by {mod}")


if __name__ == "__main__":
    main()
