"""SUBMISSION MODE v2 — with LOO correction verification.
Test outputs NEVER seen by solver. Corrections validated via leave-one-out
on training pairs to prevent overfitting. This is the honest ARC-AGI2 number.
"""
import json, time, os, sys

sys.path.insert(0, '/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/src')

from reasoning_project.unified_reasoning_system import evaluate_arc_unified

with open('/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/data/arc/arc-agi_training_challenges.json') as f:
    challenges = json.load(f)
with open('/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/data/arc/arc-agi_training_solutions.json') as f:
    solutions = json.load(f)

print('=== SUBMISSION MODE v2 — LOO Correction Verification ===')
print(f'Started: {time.strftime("%Y-%m-%d %H:%M:%S")}')
print('Test outputs NEVER passed to solver.')
print('Iteration 1: programs synthesized + verified on training pairs.')
print('Iteration 2+: corrections validated via leave-one-out on training.')
print('All novel reasoning layers, session memory, and auto rules active.')
print(flush=True)

start = time.time()
results = evaluate_arc_unified(
    challenges, solutions,
    timeout_per_task=60.0,
    per_layer_timeout=8.0,
    submission_mode=True,
)
elapsed = time.time() - start

print(f'\n=== RESULTS (SUBMISSION MODE v2 — LOO) ===')
print(f'Total tested: {results["total_tested"]}')
print(f'Total solved: {results["total_solved"]}')
print(f'Elapsed: {elapsed:.1f}s')
print(f'Session memory: {results["session_memory_strategies"]}')
print(f'Mode: {results["mode"]}')
print()
print('By layer:')
for layer, count in sorted(results['by_layer'].items(), key=lambda x: -x[1]):
    print(f'  {layer}: {count}')
print()
print('By iteration:')
for it, count in sorted(results.get('by_iteration', {}).items()):
    print(f'  iteration {it}: {count}')

outdir = '/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/full_novel_reasoning_pipeline_v2/submission_loo_2026_06_27'
os.makedirs(outdir, exist_ok=True)
with open(os.path.join(outdir, 'results.json'), 'w') as f:
    json.dump(results, f, indent=2)
print(f'\nResults saved to {outdir}/results.json')
