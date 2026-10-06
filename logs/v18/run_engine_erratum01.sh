#!/usr/bin/env bash
cd /deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti
.venv_arc2026/bin/python -m pytest tests/test_v18_proposer.py -m engine -v -p no:cacheprovider > logs/v18/engine_tests_erratum01.log 2>&1
echo "engine exit $?" >> logs/v18/engine_tests_erratum01.log
