"""Re-hash the frozen component used by U5's probes (U2's byte-extracted systems, against SYSTEMS_MANIFEST.json) and
both package manifests (against their frozen sha256). Appends to U5's own log; writes nothing in U2's folder.
Usage: python3 -I verify_systems_u5.py STAGE"""
import hashlib
import json
import os
import sys
import time

R = "/path/to/repository"
U2 = os.path.join(R, "experiments/universality_similar_problems_20261102")
LOG = "/path/to/bio_data/work/verify_log.jsonl"
MAN = {os.path.join(R, "experiments/cora_cast_20261026/kaggle_pkg/MANIFEST.json"):
       "acd57e12f6d7b2735821c06d9dfbcfafd3eaf5754383bd62a92956fd5d2d8f7a",
       os.path.join(R, "experiments/cora_cast_20261026/kaggle_pkg/cast_selective_v2/MANIFEST.json"):
       "aa8551ad935722ed0775570ff1bb1173108a777d3befead17eaf5ce57251f7d0"}
h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()      # noqa: E731
sm = json.load(open(os.path.join(U2, "SYSTEMS_MANIFEST.json")))
bad, n = [], 0
for rel, want in sm["systems"]["h"].items():
    n += 1
    p = os.path.join(U2, "systems", "h", rel)
    if not os.path.exists(p) or h(p) != want:
        bad.append(f"h/{rel}")
for p, want in MAN.items():
    n += 1
    if h(p) != want:
        bad.append(p)
rec = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "stage": sys.argv[1] if len(sys.argv) > 1 else "manual",
       "checked": n, "mismatches": bad, "ok": not bad}
os.makedirs(os.path.dirname(LOG), exist_ok=True)
open(LOG, "a").write(json.dumps(rec) + "\n")
print(json.dumps(rec))
sys.exit(0 if not bad else 1)
