#!/bin/sh
# Phase 1: Athe speed reference, feasibility summary and power (one CPU slot).
cd /path/to/repository/experiments/natural_growth_20261105
PY=python3
CTRL=feasibility/controller_source_shard0.jsonl,feasibility/controller_source_shard1.jsonl
$PY -I run.py bench bench/BENCH_ATHE_REFERENCE.json; echo "BENCH EXIT $?"
$PY -I run.py feasibility $CTRL feasibility/grow feasibility/FEASIBILITY.json > logs/feasibility_brief.json; echo "FEAS EXIT $?"
$PY -I run.py power feasibility/FEASIBILITY.json feasibility/grow power/POWER.json > logs/power_brief.json; echo "POWER EXIT $?"
echo EXIT
