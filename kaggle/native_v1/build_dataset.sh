#!/usr/bin/env bash
# Build the NATIVE_BASELINE native_v1 Kaggle dataset: the sealed native solver
# code and the two sealed object-layer assets, plus MANIFEST.json (sha256 of
# every packaged file). No data, no outputs, no research packages (no cora_*).
# Output: kaggle/native_v1/arc_native_baseline_v1.tar.gz (attach as a Kaggle Dataset).
set -eu
cd "$(dirname "$0")/../.."
OUT=kaggle/native_v1/arc_native_baseline_v1.tar.gz
echo "cdacd018da0bd9a3fa460c23beeff89fd5b0c5a85d70ecca276fe212df13ce03  library.json" | sha256sum -c -
echo "b1f07ba5f4337cf450b9c13cc142937c1c56b0dcc10e1796e6fcdb39fe2b585c  learned_verbs.json" | sha256sum -c -
STAGE=$(mktemp -d)
tar cf - --exclude='__pycache__' --exclude='*.pyc' --exclude='geocat_arc/artifacts' \
  geocat_arc harness src/reasoning_project scripts/run_unified_harness.py scripts/make_submission_v2.py \
  library.json learned_verbs.json | tar xf - -C "$STAGE"
python3 - "$STAGE" <<'PY'
import hashlib, json, os, sys
root = sys.argv[1]
files = {}
for d, dirs, fs in os.walk(root):
    dirs.sort()
    for f in sorted(fs):
        p = os.path.join(d, f)
        files[os.path.relpath(p, root)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
json.dump({"label": "NATIVE_BASELINE", "version": "native_v1", "files": files}, open(os.path.join(root, "MANIFEST.json"), "w"),
          indent=1, sort_keys=True)
print("files:", len(files))
PY
tar cf - --sort=name --mtime="2026-10-12 00:00:00" --owner=0 --group=0 --numeric-owner -C "$STAGE" . | gzip -n > "$OUT"
cp "$STAGE/MANIFEST.json" kaggle/native_v1/PACKAGE_MANIFEST.json
rm -rf "$STAGE"
sha256sum "$OUT"
