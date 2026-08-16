#!/usr/bin/env bash
# Build the Kaggle dataset tarball: code + frozen library, nothing else.
# Output: kaggle/arc_certified_solver_v21.tar.gz  (attach as a Kaggle Dataset)
# v21 sealed: 177/1000, ARC_GENERATIVE + frames + learned generators + ARC_PATTERN_DERIVE
set -eu
cd "$(dirname "$0")/.."
OUT=kaggle/arc_certified_solver_v21.tar.gz
tar czf "$OUT" \
  --exclude='__pycache__' --exclude='*.pyc' \
  geocat_arc harness src/reasoning_project \
  scripts/run_unified_harness.py scripts/make_submission_v2.py \
  outputs/unified_harness_v21/object/library.json
echo "dataset -> $OUT ($(du -h "$OUT" | cut -f1))"
