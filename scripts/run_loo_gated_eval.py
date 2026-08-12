"""SUBMISSION MODE v5 — LOO-Gated Replacement.

Key change: after reason_unified returns a solver_local_rule with LOO=0/N,
the evaluation harness tries alternative solver layers. If any alternative
passes training verification, it replaces the local rule.

This avoids cascade effects from changing reason_unified internals while
recovering ~20+ tasks where solver_local_rule overfits but a different
solver family generalizes.

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
print('LOO-GATED ACCEPTANCE — Submission Mode v5')
print('=' * 70)
print(f'Started: {time.strftime("%Y-%m-%d %H:%M:%S")}')
print()
print('Changes from v4:')
print('  - Post-iter1 LOO-gated replacement (no cascade effects)')
print('  - solver_local_rule with LOO=0/N replaced by alternative solvers')
print('  - LOO-residual correction available in iter2')
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
print('RESULTS — LOO-GATED v5')
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

# Track LOO-gated vs direct
loo_gated = sum(1 for s in results['solved'] if 'loo_residual' in s.get('layer', ''))
deferred_fallback = sum(1 for s in results['solved']
                        if s.get('family', '') == 'solver_local_rule'
                        and s.get('layer', '').count('+') == 0)
print(f'LOO-residual corrections: {loo_gated}')
print(f'Direct solver_local_rule (passed LOO or fallback): {deferred_fallback}')

outdir = '/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/full_novel_reasoning_pipeline_v2/loo_replace_v5b_2026_06_28'
os.makedirs(outdir, exist_ok=True)
with open(os.path.join(outdir, 'results.json'), 'w') as f:
    json.dump(results, f, indent=2)
print(f'\nResults saved to {outdir}/results.json')
