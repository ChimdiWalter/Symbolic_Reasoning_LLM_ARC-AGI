#!/usr/bin/env bash
# Build the Kaggle dataset tarball: code + the sealed object-layer assets, nothing else.
# Output: kaggle/arc_certified_solver_v23.tar.gz  (attach as a Kaggle Dataset)
# v23 sealed: 185/1000 (183 in-run + 2 arbitration recoveries) with the five chain flags
# ARC_DIHEDRAL_FRAMES=45 ARC_GENERATIVE=1 ARC_PATTERN_DERIVE=1 ARC_VARIANT_BUDGET=1 ARC_RAY_EXT=1
# (set by kaggle_notebook.py for the harness subprocess) and library.json + learned_verbs.json
# (records/NATIVE_ASSETS_PROVENANCE.md). No data, no outputs, no research packages.
set -eu
cd "$(dirname "$0")/.."
OUT=kaggle/arc_certified_solver_v23.tar.gz
echo "cdacd018da0bd9a3fa460c23beeff89fd5b0c5a85d70ecca276fe212df13ce03  library.json" | sha256sum -c -
echo "b1f07ba5f4337cf450b9c13cc142937c1c56b0dcc10e1796e6fcdb39fe2b585c  learned_verbs.json" | sha256sum -c -
tar czf "$OUT" \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='geocat_arc/artifacts' \
  geocat_arc harness src/reasoning_project \
  scripts/run_unified_harness.py scripts/make_submission_v2.py \
  library.json learned_verbs.json
echo "dataset -> $OUT ($(du -h "$OUT" | cut -f1))"
