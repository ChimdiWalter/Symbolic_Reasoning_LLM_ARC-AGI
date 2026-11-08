"""Hash gate (stdlib only; run as python3 -I cgrow/u3/verify_freeze.py FREEZE_JSON BASE_DIR): exits 1 unless every
file listed in FREEZE_JSON["files_sha256"] (paths relative to BASE_DIR) has exactly the recorded sha256."""
import hashlib
import json
import os
import sys

freeze, base = sys.argv[1], sys.argv[2]
with open(freeze, encoding="utf-8") as f:
    files = json.load(f)["files_sha256"]
bad = []
for rel, want in sorted(files.items()):
    p = os.path.join(base, rel)
    try:
        with open(p, "rb") as f:
            got = hashlib.sha256(f.read()).hexdigest()
    except OSError:
        got = None
    if got != want:
        bad.append(rel)
print(json.dumps({"checked": len(files), "mismatched": bad}))
sys.exit(1 if bad else 0)
