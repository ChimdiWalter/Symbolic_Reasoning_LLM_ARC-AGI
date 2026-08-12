#!/bin/bash
#SBATCH --job-name=7layer_fix
#SBATCH --partition=requeue
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/full_novel_reasoning_pipeline_v2/unified_7layer_bugfix_2026_06_25/slurm_%j.out
#SBATCH --error=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/full_novel_reasoning_pipeline_v2/unified_7layer_bugfix_2026_06_25/slurm_%j.err

source /cluster/VAST/kazict-lab/e/lesion_phes/lesenv/bin/activate
export PYTHONPATH=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/src

OUTDIR=/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/outputs/full_novel_reasoning_pipeline_v2/unified_7layer_bugfix_2026_06_25

python3.11 -u -c "
import json, time, os

from reasoning_project.unified_reasoning_system import evaluate_arc_unified

with open('/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/data/arc/arc-agi_training_challenges.json') as f:
    challenges = json.load(f)
with open('/cluster/VAST/kazict-lab/e/lesion_phes/code/Reasoning_Project/data/arc/arc-agi_training_solutions.json') as f:
    solutions = json.load(f)

print('Running Unified 7-Layer (BUGFIX) on ARC-1000...')
print('Fixes: adaptive_reasoner indentation, fill_changed generalization,')
print('       expanded residual correction, expanded compositional search,')
print('       multi-bg composable, layer reorder fix')
print(flush=True)

start = time.time()
results = evaluate_arc_unified(
    challenges, solutions,
    timeout_per_task=30.0,
    per_layer_timeout=5.0,
)
elapsed = time.time() - start

print(f'=== UNIFIED SYSTEM RESULTS (7 layers, BUGFIX) ===')
print(f'Total tested: {results[\"total_tested\"]}')
print(f'Total solved: {results[\"total_solved\"]}')
print(f'Elapsed: {elapsed:.1f}s')
print(f'Session memory strategies: {results[\"session_memory_strategies\"]}')
print()
print('By layer:')
for layer, count in sorted(results['by_layer'].items(), key=lambda x: -x[1]):
    print(f'  {layer}: {count}')
print()
print('By family:')
for fam, count in sorted(results['by_family'].items(), key=lambda x: -x[1]):
    print(f'  {fam}: {count}')
print()
print('Solved task IDs:')
for s in sorted(results['solved'], key=lambda x: x['task_id']):
    print(f'  {s[\"task_id\"]}: layer={s[\"layer\"]}, family={s[\"family\"]}')

outdir = '${OUTDIR}'
with open(os.path.join(outdir, 'results.json'), 'w') as f:
    json.dump(results, f, indent=2)
print(f'Results saved to {outdir}/results.json')
"
