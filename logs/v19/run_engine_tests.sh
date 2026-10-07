#!/usr/bin/env bash
cd /deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026 || exit 1
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
unset $(env | grep -o '^ARC_[A-Za-z0-9_]*' | tr '\n' ' ') 2>/dev/null
{
echo "== engine's own tests, excluding test_segmentation_features.py (reads ARC training data) and"
echo "   test_round9_delta_certificates.py (imports scripts/meta_m3_delta_certificates.py, absent since a44d262)"
timeout 5400 .venv_arc2026/bin/python -m pytest -q -p no:cacheprovider geocat_arc/object_reasoning/tests \
  --ignore=geocat_arc/object_reasoning/tests/test_segmentation_features.py \
  --ignore=geocat_arc/object_reasoning/tests/test_round9_delta_certificates.py -rfE 2>&1 | grep -E "^(FAILED|ERROR) |passed|failed"
echo "== done $(date -u +%FT%TZ)"
} > logs/v19/engine_own_tests.log 2>&1
touch logs/v19/ENGINE_TESTS_DONE
