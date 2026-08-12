"""SUBMISSION MODE v4 — Cortical Reasoning Model.

Six brain-inspired cognitive mechanisms, no test output leakage:
1. Hierarchical Perception (V1→V4): multi-level grid representation
2. Structural Hypothesis Correction (Predictive Coding): low-parameter LOO-validated
3. Multi-Column Voting (Thousand Brains): consensus across imperfect candidates
4. Metacognitive Confidence: calibrated near-miss acceptance
5. Feature Binding (Cortical Oscillations): compose correct aspects from different solvers
6. Structural Session Memory (Analogical Reasoning): transfer by structural signature
+ Session memory bug fix (submission mode now records insights)

Test outputs NEVER passed to solver. All corrections LOO-validated.
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
print('CORTICAL REASONING MODEL — Submission Mode v4')
print('=' * 70)
print(f'Started: {time.strftime("%Y-%m-%d %H:%M:%S")}')
print()
print('Cognitive Mechanisms Active:')
print('  1. Hierarchical Perception (V1→V4 cortical hierarchy)')
print('  2. Structural Hypothesis Correction (Predictive Coding)')
print('  3. Multi-Column Voting (Thousand Brains / cortical columns)')
print('  4. Metacognitive Confidence (calibrated near-miss acceptance)')
print('  5. Feature Binding (cortical oscillations)')
print('  6. Structural Session Memory (analogical reasoning)')
print()
print('Test outputs: NEVER passed to solver')
print('Correction validation: LOO on training pairs')
print('Session memory: ACTIVE (bug fixed)')
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
print('RESULTS — CORTICAL REASONING MODEL')
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

print('By family (top 20):')
for fam, count in sorted(results.get('by_family', {}).items(), key=lambda x: -x[1])[:20]:
    print(f'  {fam}: {count}')
print()

# Categorize cortical mechanism contributions
cortical_layers = {
    'structural': 0, 'cortical_vote': 0, 'metacognitive': 0,
    'feature_binding': 0, 'correction': 0, 'iter1_direct': 0
}
for s in results['solved']:
    layer = s.get('layer', '')
    if 'structural' in layer:
        cortical_layers['structural'] += 1
    elif 'cortical_vote' in layer:
        cortical_layers['cortical_vote'] += 1
    elif 'metacognitive' in layer:
        cortical_layers['metacognitive'] += 1
    elif 'feature_binding' in layer:
        cortical_layers['feature_binding'] += 1
    elif 'correction' in layer:
        cortical_layers['correction'] += 1
    else:
        cortical_layers['iter1_direct'] += 1

print('Cortical mechanism contributions:')
for mech, count in cortical_layers.items():
    if count > 0:
        print(f'  {mech}: {count}')

outdir = '/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/full_novel_reasoning_pipeline_v2/cortical_reasoning_v4_2026_06_28'
os.makedirs(outdir, exist_ok=True)
with open(os.path.join(outdir, 'results.json'), 'w') as f:
    json.dump(results, f, indent=2)
print(f'\nResults saved to {outdir}/results.json')
