#!/usr/bin/env bash
# Build the Kaggle dataset tarball: code + frozen library, nothing else.
# Output: kaggle/arc_certified_solver.tar.gz  (attach as a Kaggle Dataset)
set -eu
cd "$(dirname "$0")/.."
OUT=kaggle/arc_certified_solver.tar.gz
tar czf "$OUT" \
  --exclude='__pycache__' --exclude='*.pyc' \
  geocat_arc harness src/reasoning_project \
  scripts/run_unified_harness.py scripts/make_submission_v2.py \
  outputs/object_reasoning_promotion_v3/library.json
echo "dataset -> $OUT ($(du -h "$OUT" | cut -f1))"
