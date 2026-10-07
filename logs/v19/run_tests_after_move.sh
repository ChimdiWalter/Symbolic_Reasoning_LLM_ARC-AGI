#!/usr/bin/env bash
cd /deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026 || exit 1
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
unset $(env | grep -o '^ARC_[A-Za-z0-9_]*' | tr '\n' ' ') 2>/dev/null
PY=.venv_arc2026/bin/python
{
echo "== v1.9 engine tests"; timeout 1800 $PY -m pytest -q -p no:cacheprovider tests/test_v19_audit.py tests/test_v19_repair.py -m engine 2>&1 | tail -3
echo "== v1.7 and v1.8 fast tests"; timeout 1800 $PY -m pytest -q -p no:cacheprovider tests/test_v17_compiler.py tests/test_v18_proposer.py -m "not engine" 2>&1 | tail -3
echo "== engine's own tests (minus test_segmentation_features.py, which reads ARC training data)"
timeout 3600 $PY -m pytest -q -p no:cacheprovider geocat_arc/object_reasoning/tests --ignore=geocat_arc/object_reasoning/tests/test_segmentation_features.py 2>&1 | tail -4
echo "== done $(date -u +%FT%TZ)"
} > logs/v19/tests_after_move.log 2>&1
touch logs/v19/TESTS_AFTER_MOVE_DONE
