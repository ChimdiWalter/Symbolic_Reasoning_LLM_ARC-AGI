#!/bin/sh
# Build arc_cora_fhr_v1.tar.gz: the CORA-FHR modules (static import closure in FILES.txt) and fhr_phase.py.
# The native engine (geocat_arc, harness) and the frozen assets come from the unchanged native_v1 dataset;
# the closure's 71 engine files were checked byte-identical to it (2026-10-15).
set -eu
cd "$(dirname "$0")/../.."
OUT=kaggle/cora_fhr_v1/arc_cora_fhr_v1.tar.gz
STAGE=$(mktemp -d)
tar cf - $(cat kaggle/cora_fhr_v1/FILES.txt) | tar xf - -C "$STAGE"
cp kaggle/cora_fhr_v1/fhr_phase.py "$STAGE/"
python3 - "$STAGE" "$(git rev-parse --short HEAD)" <<'PY'
import hashlib, json, os, sys
root, commit = sys.argv[1], sys.argv[2]
files = {}
for d, dirs, fs in os.walk(root):
    dirs.sort()
    for f in sorted(fs):
        p = os.path.join(d, f)
        files[os.path.relpath(p, root)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
json.dump({"label": "CORA_FHR_V1", "version": "cora_fhr_v1", "source_commit": commit, "files": files},
          open(os.path.join(root, "MANIFEST.json"), "w"), indent=1, sort_keys=True)
print("files:", len(files))
PY
tar cf - --sort=name --mtime="2026-10-15 00:00:00" --owner=0 --group=0 --numeric-owner -C "$STAGE" . | gzip -n > "$OUT"
cp "$STAGE/MANIFEST.json" kaggle/cora_fhr_v1/PACKAGE_MANIFEST.json
rm -rf "$STAGE"
sha256sum "$OUT"
