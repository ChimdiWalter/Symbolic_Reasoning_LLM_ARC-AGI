"""Fetch a finished kernel's outputs and place its run records under OUT_DIR/<BENCH>/ (standard library plus the
Kaggle command-line tool).

    python3 -I objgrow/kaggle_fetch.py BENCH OUT_DIR [TAG]        TAG: the kernel's name suffix (for example -v2)

Downloads <KERNEL>_outputs.tar.gz into logs/kaggle_out/<KERNEL>/, records its sha256, unpacks it, and copies
run/<BENCH>/{units*.json, registry.json} to OUT_DIR/<BENCH>/ and the gate caches to logs/cache/. Refuses an archive
that holds anything but these records.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KAGGLE = os.path.expanduser("kaggle")
SLUG = {"1d_arc": "1d", "concept_arc": "concept", "mini_arc": "mini"}


def main(bench, out_dir, tag=""):
    kernel = "OG" + SLUG[bench].upper() + tag.upper()
    kid = f"chimdiwalter/cora-object-growth-{SLUG[bench]}{tag}"
    d = os.path.join(STUDY, "logs", "kaggle_out", kernel)
    os.makedirs(d, exist_ok=True)
    subprocess.run([KAGGLE, "kernels", "output", kid, "-p", d, "--force"], check=True)
    arc = os.path.join(d, f"{kernel}_outputs.tar.gz")
    digest = hashlib.sha256(open(arc, "rb").read()).hexdigest()
    with tarfile.open(arc) as tf:
        names = tf.getnames()
        bad = [n for n in names if not (n.startswith("run") or n.startswith("cache"))]
        if bad:
            raise SystemExit(f"unexpected archive content: {bad[:5]}")
        tf.extractall(os.path.join(d, "unpacked"))
    src = os.path.join(d, "unpacked", "run", bench)
    dst = os.path.join(os.path.abspath(out_dir), bench)
    os.makedirs(dst, exist_ok=True)
    copied = []
    for fn in sorted(os.listdir(src)):
        if fn.endswith(".json"):
            shutil.copy(os.path.join(src, fn), os.path.join(dst, fn))
            copied.append(fn)
    cdir = os.path.join(d, "unpacked", "cache")
    if os.path.isdir(cdir):
        os.makedirs(os.path.join(STUDY, "logs", "cache"), exist_ok=True)
        for fn in os.listdir(cdir):
            shutil.copy(os.path.join(cdir, fn), os.path.join(STUDY, "logs", "cache", fn))
    rec = {"kernel": kid, "archive_sha256": digest, "copied": copied, "log": os.path.join(d, kernel + ".log")}
    with open(os.path.join(dst, "KAGGLE_FETCH.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    print(json.dumps(rec))


if __name__ == "__main__":
    main(*sys.argv[1:])
