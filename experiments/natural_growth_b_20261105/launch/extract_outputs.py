"""Extract a rehearsal kernel's returned archive: checks/kaggle_rehearsal/rehearsal_<N>/download/<K>/<K>_outputs.tar.gz
-> checks/kaggle_rehearsal/rehearsal_<N>/extracted/<K>/ (a new folder; members must lie under <K>/; tarfile's 'data'
filter).

    python3 -I launch/extract_outputs.py N K
"""
import hashlib
import os
import sys
import tarfile

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REC = os.path.join(STUDY, "checks", "kaggle_rehearsal", f"rehearsal_{int(sys.argv[1])}")
k = sys.argv[2]
assert k in ("RA", "RB", "RC")
src = os.path.join(REC, "download", k, f"{k}_outputs.tar.gz")
dst = os.path.join(REC, "extracted")
if os.path.exists(os.path.join(dst, k)):
    raise SystemExit(f"extracted/{k} exists; not overwritten")
os.makedirs(dst, exist_ok=True)
with tarfile.open(src, "r:gz") as tf:
    names = tf.getnames()
    bad = [n for n in names if not (n == k or n.startswith(k + "/"))]
    if bad:
        raise SystemExit(f"members outside {k}/: {bad[:5]}")
    tf.extractall(dst, filter="data")
print(k, hashlib.sha256(open(src, "rb").read()).hexdigest(), len(names), "members")
