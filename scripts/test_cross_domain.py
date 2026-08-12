#!/usr/bin/env python3
"""Cross-domain evaluation of StructuralReasoner + domain adapters.

Tests:
1. StructuralReasoner with GridDomainAdapter on grid tasks
2. StructuralReasoner with GraphDomainAdapter on graph tasks
3. StructuralReasoner with ChessBoardDomainAdapter on board tasks
4. StructuralReasoner with MoleculeGraphDomainAdapter on molecule tasks
5. AdapterGenesis auto-synthesis on all domains
6. Counterfactual invariance on grid tasks
7. OOD scaling on grid tasks
8. Concept recombination on grid tasks

Same reasoning engine for all domains — only the adapter changes.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reasoning_project.reasoning_engine import (
    GridDomainAdapter, StructuralReasoner, ReasoningMemory,
)
from reasoning_project.domain_adapters import (
    GraphDomainAdapter, ChessBoardDomainAdapter, MoleculeGraphDomainAdapter,
)
from reasoning_project.adapter_genesis import AdapterGenesis, AdapterMemory
from reasoning_project.benchmark_generator import AdaptiveReasoningSuite


def test_domain(adapter, reasoner, tasks, domain_name):
    """Test a StructuralReasoner + adapter on a set of tasks."""
    correct = 0
    wrong = 0
    no_answer = 0
    results = []

    for task in tasks:
        result = reasoner.solve(task.train_pairs, [task.test_pairs[0][0]])
        expected = task.test_pairs[0][1]

        if result is None:
            no_answer += 1
            results.append((task.task_id, 'no_answer', None))
        else:
            preds, meta = result
            if adapter.scenes_equal(preds[0], expected):
                correct += 1
                results.append((task.task_id, 'correct', meta))
            else:
                wrong += 1
                results.append((task.task_id, 'wrong', meta))

    return {
        'domain': domain_name,
        'total': len(tasks),
        'correct': correct,
        'wrong': wrong,
        'no_answer': no_answer,
        'results': results,
    }


def test_adapter_genesis(genesis, tasks, domain_name):
    """Test AdapterGenesis auto-synthesis on tasks."""
    correct = 0
    wrong = 0
    no_answer = 0
    adapter_synth = 0
    results = []

    for task in tasks:
        result = genesis.synthesize_and_solve(
            task.train_pairs,
            [task.test_pairs[0][0]],
        )
        expected = task.test_pairs[0][1]

        if result is None:
            no_answer += 1
            results.append((task.task_id, 'no_answer', None))
        else:
            preds, meta = result
            adapter_synth += 1
            import numpy as np
            if isinstance(expected, np.ndarray):
                eq = np.array_equal(np.asarray(preds[0]), expected)
            elif isinstance(expected, dict):
                eq = (preds[0] == expected)
            else:
                eq = (preds[0] == expected)

            if eq:
                correct += 1
                results.append((task.task_id, 'correct', meta))
            else:
                wrong += 1
                results.append((task.task_id, 'wrong', meta))

    return {
        'domain': f'{domain_name}_genesis',
        'total': len(tasks),
        'correct': correct,
        'wrong': wrong,
        'no_answer': no_answer,
        'adapters_synthesized': adapter_synth,
        'results': results,
    }


def main():
    t0 = time.time()

    # Build benchmark suite
    suite = AdaptiveReasoningSuite(seed=42)
    tasks = suite.build_all()
    print(suite.summary(tasks))
    print()

    # --- Test 1: Grid tasks with GridDomainAdapter ---
    grid_adapter = GridDomainAdapter()
    grid_reasoner = StructuralReasoner(grid_adapter)
    grid_result = test_domain(
        grid_adapter, grid_reasoner, tasks['atomic_grid'], 'grid',
    )
    print(f"[Grid/GridAdapter]  {grid_result['correct']}/{grid_result['total']} correct, "
          f"{grid_result['wrong']} FP, {grid_result['no_answer']} no answer")
    for tid, status, meta in grid_result['results']:
        detail = f"  strategy={meta.get('strategy', '?')}" if meta else ""
        print(f"  {tid}: {status}{detail}")

    # --- Test 2: Graph tasks with GraphDomainAdapter ---
    graph_adapter = GraphDomainAdapter()
    graph_reasoner = StructuralReasoner(graph_adapter)
    graph_result = test_domain(
        graph_adapter, graph_reasoner, tasks['graph'], 'graph',
    )
    print(f"\n[Graph/GraphAdapter]  {graph_result['correct']}/{graph_result['total']} correct, "
          f"{graph_result['wrong']} FP, {graph_result['no_answer']} no answer")
    for tid, status, meta in graph_result['results']:
        detail = f"  strategy={meta.get('strategy', '?')}" if meta else ""
        print(f"  {tid}: {status}{detail}")

    # --- Test 3: Chess tasks with ChessBoardDomainAdapter ---
    chess_adapter = ChessBoardDomainAdapter()
    chess_reasoner = StructuralReasoner(chess_adapter)
    chess_result = test_domain(
        chess_adapter, chess_reasoner, tasks['chess'], 'chess',
    )
    print(f"\n[Chess/ChessAdapter]  {chess_result['correct']}/{chess_result['total']} correct, "
          f"{chess_result['wrong']} FP, {chess_result['no_answer']} no answer")
    for tid, status, meta in chess_result['results']:
        detail = f"  strategy={meta.get('strategy', '?')}" if meta else ""
        print(f"  {tid}: {status}{detail}")

    # --- Test 4: Molecule tasks with MoleculeGraphDomainAdapter ---
    mol_adapter = MoleculeGraphDomainAdapter()
    mol_reasoner = StructuralReasoner(mol_adapter)
    mol_result = test_domain(
        mol_adapter, mol_reasoner, tasks['molecule'], 'molecule',
    )
    print(f"\n[Molecule/MolAdapter]  {mol_result['correct']}/{mol_result['total']} correct, "
          f"{mol_result['wrong']} FP, {mol_result['no_answer']} no answer")
    for tid, status, meta in mol_result['results']:
        detail = f"  strategy={meta.get('strategy', '?')}" if meta else ""
        print(f"  {tid}: {status}{detail}")

    # --- Test 5: Recombination tasks ---
    recom_result = test_domain(
        grid_adapter, grid_reasoner, tasks['recombination'], 'recombination',
    )
    print(f"\n[Recombination/GridAdapter]  {recom_result['correct']}/{recom_result['total']} correct, "
          f"{recom_result['wrong']} FP, {recom_result['no_answer']} no answer")
    for tid, status, meta in recom_result['results']:
        detail = f"  strategy={meta.get('strategy', '?')}" if meta else ""
        print(f"  {tid}: {status}{detail}")

    # --- Test 6: Counterfactual invariance ---
    cf_result = test_domain(
        grid_adapter, grid_reasoner, tasks['counterfactual'], 'counterfactual',
    )
    print(f"\n[Counterfactual/GridAdapter]  {cf_result['correct']}/{cf_result['total']} correct, "
          f"{cf_result['wrong']} FP, {cf_result['no_answer']} no answer")
    for tid, status, meta in cf_result['results']:
        detail = f"  strategy={meta.get('strategy', '?')}" if meta else ""
        print(f"  {tid}: {status}{detail}")

    # --- Test 7: AdapterGenesis auto-synthesis ---
    print("\n--- AdapterGenesis Auto-Synthesis ---")
    genesis = AdapterGenesis()
    all_tasks = []
    for cat, cat_tasks in tasks.items():
        if cat not in ('counterfactual',):  # skip counterfactual variants
            all_tasks.extend(cat_tasks)

    genesis_result = test_adapter_genesis(genesis, all_tasks, 'all')
    print(f"\n[AdapterGenesis/All]  {genesis_result['correct']}/{genesis_result['total']} correct, "
          f"{genesis_result['wrong']} FP, {genesis_result['no_answer']} no answer, "
          f"{genesis_result['adapters_synthesized']} adapters synthesized")
    for tid, status, meta in genesis_result['results']:
        detail = ""
        if meta:
            detail = f"  schema={meta.get('adapter_schema', '?')} domain={meta.get('adapter_domain', '?')}"
        print(f"  {tid}: {status}{detail}")

    # --- Summary ---
    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print("CROSS-DOMAIN EVALUATION SUMMARY")
    print(f"{'='*60}")
    all_results = [grid_result, graph_result, chess_result, mol_result,
                   recom_result, cf_result]
    total_correct = sum(r['correct'] for r in all_results)
    total_wrong = sum(r['wrong'] for r in all_results)
    total_tasks = sum(r['total'] for r in all_results)
    total_no = sum(r['no_answer'] for r in all_results)

    for r in all_results:
        print(f"  {r['domain']:20s}: {r['correct']}/{r['total']} correct, "
              f"{r['wrong']} FP, {r['no_answer']} no answer")
    print(f"  {'TOTAL':20s}: {total_correct}/{total_tasks} correct, "
          f"{total_wrong} FP, {total_no} no answer")
    print(f"\n  AdapterGenesis: {genesis_result['correct']}/{genesis_result['total']} correct, "
          f"{genesis_result['wrong']} FP")
    print(f"\n  Time: {elapsed:.1f}s")

    if total_wrong == 0 and genesis_result['wrong'] == 0:
        print("\n  0 FALSE POSITIVES — SOUNDNESS MAINTAINED ACROSS ALL DOMAINS")
    else:
        print(f"\n  WARNING: {total_wrong + genesis_result['wrong']} false positives detected")


if __name__ == "__main__":
    main()
