#!/usr/bin/env bash
# Item-2 v1.7 erratum 01: engine tests, then the development dry run, in sequence.
cd /deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 .venv_arc2026/bin/python -m pytest tests/test_v17_compiler.py -m engine -v -p no:cacheprovider > logs/v17/engine_tests_erratum01.log 2>&1
echo "engine exit $?" >> logs/v17/engine_tests_erratum01.log
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_tti .venv_arc2026/bin/python logs/v17/dryrun_dev.py > logs/v17/acceptance_dryrun_dev_erratum01.log 2>&1
echo "dryrun exit $?" >> logs/v17/acceptance_dryrun_dev_erratum01.log
