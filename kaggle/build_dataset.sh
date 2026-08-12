#!/usr/bin/env bash
# Build the Kaggle dataset tarball: code + frozen library, nothing else.
# Output: kaggle/arc_certified_solver_v20.tar.gz  (attach as a Kaggle Dataset)
# v20 sealed: 174/1000, ARC_GENERATIVE + frames + learned generators
set -eu
cd "$(dirname "$0")/.."
OUT=kaggle/arc_certified_solver_v20.tar.gz
tar czf "$OUT" \
  --exclude='__pycache__' --exclude='*.pyc' \
  geocat_arc harness src/reasoning_project \
  scripts/run_unified_harness.py scripts/make_submission_v2.py \
  outputs/unified_harness_v20/object/library.json
echo "dataset -> $OUT ($(du -h "$OUT" | cut -f1))"
