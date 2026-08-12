"""SUBMISSION MODE v6b — Extended LOO-Replace + Cortical Post-Processing.

Key changes from v5b:
  - LOO-replace now catches meta_solver_local_rule and meta_color families
    (previously only solver_local_rule/solver_color_solver were gated)
  - When LOO-replace runs alternative layers, partial candidates are collected
    and cortical reasoning (structural corrections, voting, binding) is applied
  - LOO validation added to cortical voting and feature binding outputs
  - reason_unified iter1 path unchanged (no cascade regressions)

Test outputs NEVER passed to solver.
"""
import json
import time
import os
import sys

sys.path.insert(0, '/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/src')

from reasoning_project.unified_reasoning_system import evaluate_arc_unified

with open('/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/data/arc/arc-agi_training_challenges.json') as f:
    challenges = json.load(f)
with open('/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/data/arc/arc-agi_training_solutions.json') as f:
    solutions = json.load(f)

print('=' * 70)
print('CORTICAL v6b — Extended LOO-Replace + Cortical Post-Processing')
print('=' * 70)
print(f'Started: {time.strftime("%Y-%m-%d %H:%M:%S")}')
print()
print('Changes from v5b:')
print('  - LOO-replace expanded: meta_solver_local_rule, meta_color families')
print('  - Cortical reasoning on LOO-replace partial candidates')
print('  - LOO validation on cortical voting/binding outputs')
print('  - reason_unified iter1 path unchanged (stable base)')
print()
print('Test outputs: NEVER passed to solver')
print(flush=True)

start = time.time()
results = evaluate_arc_unified(
    challenges, solutions,
    timeout_per_task=60.0,
    per_layer_timeout=8.0,
    submission_mode=True,
)
elapsed = time.time() - start

print()
print('=' * 70)
print('RESULTS — CORTICAL v6b')
print('=' * 70)
print(f'Total tested: {results["total_tested"]}')
print(f'Total solved: {results["total_solved"]}')
print(f'Elapsed: {elapsed:.1f}s ({elapsed/60:.1f} min)')
print(f'Session memory strategies: {results["session_memory_strategies"]}')
print(f'Mode: {results["mode"]}')
print()

print('By layer:')
for layer, count in sorted(results['by_layer'].items(), key=lambda x: -x[1]):
    print(f'  {layer}: {count}')
print()

print('By iteration:')
for it, count in sorted(results.get('by_iteration', {}).items()):
    print(f'  iteration {it}: {count}')
print()

print('By family (top 25):')
for fam, count in sorted(results.get('by_family', {}).items(), key=lambda x: -x[1])[:25]:
    print(f'  {fam}: {count}')
print()

# Categorize contributions
cats = {
    'structural': 0, 'cortical_vote': 0, 'metacognitive': 0,
    'feature_binding': 0, 'loo_replace': 0, 'correction': 0,
    'loo_residual': 0, 'iter1_direct': 0,
}
for s in results['solved']:
    layer = s.get('layer', '')
    if 'structural' in layer:
        cats['structural'] += 1
    elif 'cortical_vote' in layer:
        cats['cortical_vote'] += 1
    elif 'metacognitive' in layer:
        cats['metacognitive'] += 1
    elif 'feature_binding' in layer:
        cats['feature_binding'] += 1
    elif 'loo_replace' in layer:
        cats['loo_replace'] += 1
    elif 'loo_residual' in layer:
        cats['loo_residual'] += 1
    elif 'correction' in layer:
        cats['correction'] += 1
    else:
        cats['iter1_direct'] += 1

print('Mechanism contributions:')
for mech, count in cats.items():
    if count > 0:
        print(f'  {mech}: {count}')

outdir = '/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/full_novel_reasoning_pipeline_v2/cortical_v6b_2026_06_30'
os.makedirs(outdir, exist_ok=True)
with open(os.path.join(outdir, 'results.json'), 'w') as f:
    json.dump(results, f, indent=2)
print(f'\nResults saved to {outdir}/results.json')
