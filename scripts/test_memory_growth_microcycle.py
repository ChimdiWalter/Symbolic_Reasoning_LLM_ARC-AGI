#!/usr/bin/env python3.11
"""Memory growth microcycle: prove that memory enables cumulative reasoning."""

import csv
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project")
sys.path.insert(0, str(PROJECT_ROOT / "src"))

OUTPUT_DIR = PROJECT_ROOT / "outputs/deep_project_completion/mechanism_repair_pass/memory_growth"

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "certificates").mkdir(exist_ok=True)

    from reasoning_project.reasoning_engine import StructuralReasoner, GridDomainAdapter, ReasoningMemory
    from reasoning_project.benchmark_generator import GridTaskGenerator

    adapter = GridDomainAdapter()

    event_chains = []
    promoted_tasks = []
    certificates = []
    results = []

    # Strategy: Use compound tasks that REQUIRE knowledge from simpler tasks.
    # Stage 1: Try compound task WITHOUT memory → should fail
    # Stage 2: Solve simple component tasks → builds memory
    # Stage 3: Retry compound task WITH memory → should succeed due to primed attention

    gen = GridTaskGenerator()

    # Define task families: simple tasks that teach concepts, compound tasks that need them
    families = []

    # Family 1: "largest" concept
    simple_tasks_1 = []
    for fn_name in ["generate_keep_largest"]:
        fn = getattr(gen, fn_name, None)
        if fn:
            try:
                simple_tasks_1.append((fn_name, fn()))
            except Exception:
                pass

    compound_tasks_1 = []
    for fn_name in ["generate_keep_largest_hollow"]:
        fn = getattr(gen, fn_name, None)
        if fn:
            try:
                compound_tasks_1.append((fn_name, fn()))
            except Exception:
                pass

    if simple_tasks_1 and compound_tasks_1:
        families.append(("largest_family", simple_tasks_1, compound_tasks_1))

    # Family 2: "smallest" + "touching" concept
    simple_tasks_2 = []
    for fn_name in ["generate_keep_smallest", "generate_keep_touching_boundary"]:
        fn = getattr(gen, fn_name, None)
        if fn:
            try:
                simple_tasks_2.append((fn_name, fn()))
            except Exception:
                pass

    compound_tasks_2 = []
    for fn_name in ["generate_keep_smallest_touching"]:
        fn = getattr(gen, fn_name, None)
        if fn:
            try:
                compound_tasks_2.append((fn_name, fn()))
            except Exception:
                pass

    if simple_tasks_2 and compound_tasks_2:
        families.append(("smallest_touching_family", simple_tasks_2, compound_tasks_2))

    # Family 3: "hollow" concept
    simple_tasks_3 = []
    for fn_name in ["generate_keep_hollow"]:
        fn = getattr(gen, fn_name, None)
        if fn:
            try:
                simple_tasks_3.append((fn_name, fn()))
            except Exception:
                pass

    compound_tasks_3 = []
    for fn_name in ["generate_keep_hollow_not_largest"]:
        fn = getattr(gen, fn_name, None)
        if fn:
            try:
                compound_tasks_3.append((fn_name, fn()))
            except Exception:
                pass

    if simple_tasks_3 and compound_tasks_3:
        families.append(("hollow_family", simple_tasks_3, compound_tasks_3))

    for family_name, simple_tasks, compound_tasks in families:
        print(f"\n=== Family: {family_name} ===")

        # STAGE 1: Try compound task WITHOUT memory (cold start)
        memory_cold = ReasoningMemory()
        reasoner_cold = StructuralReasoner(adapter, memory=memory_cold)

        for task_name, task in compound_tasks:
            test_inputs = [t[0] for t in task.test_pairs]
            expected = [t[1] for t in task.test_pairs]

            cold_solved = False
            cold_strategy = ""
            try:
                result = reasoner_cold.solve(task.train_pairs, test_inputs)
                if result:
                    preds, meta = result
                    cold_solved = all(adapter.scenes_equal(p, e) for p, e in zip(preds, expected))
                    cold_strategy = meta.get("strategy", "")
            except Exception as e:
                cold_strategy = f"error: {e}"

            event_chains.append({
                "family": family_name,
                "stage": "cold_attempt",
                "task": task_name,
                "solved": cold_solved,
                "strategy": cold_strategy,
                "memory_size": 0,
                "timestamp": datetime.now().isoformat(),
            })

            results.append({
                "family": family_name,
                "stage": "1_cold",
                "task": task_name,
                "solved": cold_solved,
                "strategy": cold_strategy,
                "memory_episodes": 0,
            })

            print(f"  Cold attempt {task_name}: solved={cold_solved}")

        # STAGE 2: Solve simple tasks to build memory (warm-up)
        memory_warm = ReasoningMemory()
        reasoner_warm = StructuralReasoner(adapter, memory=memory_warm)

        for task_name, task in simple_tasks:
            test_inputs = [t[0] for t in task.test_pairs]
            expected = [t[1] for t in task.test_pairs]

            warm_solved = False
            warm_strategy = ""
            try:
                result = reasoner_warm.solve(task.train_pairs, test_inputs)
                if result:
                    preds, meta = result
                    warm_solved = all(adapter.scenes_equal(p, e) for p, e in zip(preds, expected))
                    warm_strategy = meta.get("strategy", "")
            except Exception as e:
                warm_strategy = f"error: {e}"

            # Count episodes stored
            n_episodes = 0
            if hasattr(memory_warm, '_episodes'):
                n_episodes = len(memory_warm._episodes)
            elif hasattr(memory_warm, 'episodes'):
                n_episodes = len(memory_warm.episodes)

            event_chains.append({
                "family": family_name,
                "stage": "warm_up",
                "task": task_name,
                "solved": warm_solved,
                "strategy": warm_strategy,
                "memory_size": n_episodes,
                "timestamp": datetime.now().isoformat(),
            })

            results.append({
                "family": family_name,
                "stage": "2_warmup",
                "task": task_name,
                "solved": warm_solved,
                "strategy": warm_strategy,
                "memory_episodes": n_episodes,
            })

            print(f"  Warm-up {task_name}: solved={warm_solved}, episodes={n_episodes}")

        # STAGE 3: Retry compound task WITH primed memory
        reasoner_primed = StructuralReasoner(adapter, memory=memory_warm)

        for task_name, task in compound_tasks:
            test_inputs = [t[0] for t in task.test_pairs]
            expected = [t[1] for t in task.test_pairs]

            warm_solved = False
            warm_strategy = ""
            try:
                result = reasoner_primed.solve(task.train_pairs, test_inputs)
                if result:
                    preds, meta = result
                    warm_solved = all(adapter.scenes_equal(p, e) for p, e in zip(preds, expected))
                    warm_strategy = meta.get("strategy", "")
            except Exception as e:
                warm_strategy = f"error: {e}"

            n_episodes = 0
            if hasattr(memory_warm, '_episodes'):
                n_episodes = len(memory_warm._episodes)
            elif hasattr(memory_warm, 'episodes'):
                n_episodes = len(memory_warm.episodes)

            event_chains.append({
                "family": family_name,
                "stage": "primed_retry",
                "task": task_name,
                "solved": warm_solved,
                "strategy": warm_strategy,
                "memory_size": n_episodes,
                "timestamp": datetime.now().isoformat(),
            })

            results.append({
                "family": family_name,
                "stage": "3_primed",
                "task": task_name,
                "solved": warm_solved,
                "strategy": warm_strategy,
                "memory_episodes": n_episodes,
            })

            # Check for memory-assisted solve
            cold_result = [r for r in results if r["family"] == family_name
                          and r["stage"] == "1_cold" and r["task"] == task_name]
            cold_was_solved = cold_result[0]["solved"] if cold_result else True

            if warm_solved and not cold_was_solved:
                promoted_tasks.append({
                    "family": family_name,
                    "task": task_name,
                    "strategy": warm_strategy,
                    "memory_episodes": n_episodes,
                    "event_chain": "failure → warmup → memory_primed → promoted",
                    "timestamp": datetime.now().isoformat(),
                })

                cert = {
                    "task_id": task_name,
                    "family": family_name,
                    "mechanism": "memory_growth",
                    "cold_solved": False,
                    "primed_solved": True,
                    "strategy": warm_strategy,
                    "memory_episodes": n_episodes,
                    "ablation": "cold_attempt_failed",
                    "timestamp": datetime.now().isoformat(),
                }
                certificates.append(cert)
                with open(OUTPUT_DIR / "certificates" / f"{family_name}_{task_name}.json", "w") as f:
                    json.dump(cert, f, indent=2)

            print(f"  Primed retry {task_name}: solved={warm_solved} (cold was {cold_was_solved})")
            if warm_solved and not cold_was_solved:
                print(f"  *** MEMORY-ASSISTED PROMOTION ***")

    # Write event chains
    with open(OUTPUT_DIR / "event_chains.jsonl", "w") as f:
        for event in event_chains:
            f.write(json.dumps(event) + "\n")

    # Write promoted tasks
    with open(OUTPUT_DIR / "promoted_tasks.jsonl", "w") as f:
        for pt in promoted_tasks:
            f.write(json.dumps(pt) + "\n")

    # Write results CSV
    csv_path = OUTPUT_DIR / "microcycle_results.csv"
    with open(csv_path, "w", newline="") as f:
        fields = ["family", "stage", "task", "solved", "strategy", "memory_episodes"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    # Write summary
    n_promoted = len(promoted_tasks)
    n_cold_failed = sum(1 for r in results if r["stage"] == "1_cold" and not r["solved"])
    n_primed_solved = sum(1 for r in results if r["stage"] == "3_primed" and r["solved"])
    n_warmup_solved = sum(1 for r in results if r["stage"] == "2_warmup" and r["solved"])

    md_path = OUTPUT_DIR / "microcycle_summary.md"
    with open(md_path, "w") as f:
        f.write(f"# Memory Growth Microcycle Summary\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        f.write("## Design\n\n")
        f.write("For each task family:\n")
        f.write("1. **Cold attempt**: Try compound task without memory → expect failure\n")
        f.write("2. **Warm-up**: Solve simpler component tasks → builds episodic memory\n")
        f.write("3. **Primed retry**: Retry compound task with memory → expect success\n\n")

        f.write("## Results\n\n")
        f.write(f"- Families tested: {len(families)}\n")
        f.write(f"- Cold failures: {n_cold_failed}\n")
        f.write(f"- Warm-up solves: {n_warmup_solved}\n")
        f.write(f"- Primed solves: {n_primed_solved}\n")
        f.write(f"- **Memory-assisted promotions: {n_promoted}**\n")
        f.write(f"- Certificates: {len(certificates)}\n\n")

        f.write("## Stage Progression\n\n")
        f.write("| Family | Stage | Task | Solved | Strategy | Episodes |\n")
        f.write("|--------|-------|------|--------|----------|----------|\n")
        for r in results:
            f.write(f"| {r['family']} | {r['stage']} | {r['task']} | {r['solved']} | "
                    f"{r['strategy']} | {r['memory_episodes']} |\n")

        if n_promoted > 0:
            f.write(f"\n## Promoted Tasks ({n_promoted})\n\n")
            for pt in promoted_tasks:
                f.write(f"- **{pt['task']}** ({pt['family']}): {pt['event_chain']}\n")
                f.write(f"  Strategy: {pt['strategy']}, Memory episodes: {pt['memory_episodes']}\n\n")

        f.write("\n## Claim Assessment\n\n")
        if n_promoted > 0:
            f.write(f"**Supported**: Memory-assisted reasoning produced {n_promoted} promotion(s) "
                    f"where cold attempts failed. The event chain "
                    f"failure→warmup→memory_primed→promoted is demonstrated.\n")
        else:
            f.write("**Not supported**: No memory-assisted promotions occurred. "
                    "The compound tasks either solved cold (no memory needed) or failed "
                    "even with memory (memory insufficient).\n")
            f.write("\nPossible explanations:\n")
            f.write("- Compound tasks may be solvable without memory (conjunction search works)\n")
            f.write("- Memory priming may not effectively change search priority\n")
            f.write("- The reasoner's exhaustive search may already find solutions without memory guidance\n")

    print(f"\nSummary: {md_path}")
    print(f"Memory-assisted promotions: {n_promoted}")
    print(f"Certificates: {len(certificates)}")


if __name__ == "__main__":
    main()
