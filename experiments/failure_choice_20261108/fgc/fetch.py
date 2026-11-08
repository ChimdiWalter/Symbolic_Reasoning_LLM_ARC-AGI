"""Check one measurement kernel's downloaded output and place its measurement files (standard library; run with -I).

    python3 -I fgc/fetch.py NAME DEST          DEST: source | test

Custody checks before anything is placed: the archive NAME_outputs.tar.gz has the sha256 that the notebook printed
in its log; every member is a regular file or folder under NAME/ (no link, absolute or parent path); the extraction
folder runs/kaggle/extract/NAME and the destination runs/DEST/measure/NAME do not exist yet. The measurement files
(share_K_W.json) are then copied to runs/DEST/measure/NAME/, with the share logs. Writes runs/kaggle/FETCH_NAME.json.
"""
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main(name, dest):
    dl = os.path.join(STUDY, "runs", "kaggle", "download", name)
    ex = os.path.join(STUDY, "runs", "kaggle", "extract", name)
    out = os.path.join(STUDY, "runs", dest, "measure", name)
    rec = {"name": name, "problems": []}
    bad = rec["problems"]
    arc = os.path.join(dl, f"{name}_outputs.tar.gz")
    if not os.path.isfile(arc):
        bad.append("no archive in the download")
    else:
        rec["archive_sha256"] = sha(arc)
        printed = set()
        for n in sorted(os.listdir(dl)):
            if n.endswith(".log"):
                with open(os.path.join(dl, n), encoding="utf-8", errors="replace") as f:
                    printed |= set(re.findall(re.escape(name) + r"_outputs\.tar\.gz ([0-9a-f]{64})", f.read()))
        rec["printed_sha256"] = sorted(printed)
        if printed != {rec["archive_sha256"]}:
            bad.append("the archive's digest differs from the printed digest (or none was printed)")
        if os.path.exists(ex) or os.path.exists(out):
            bad.append("the extraction folder or the destination exists already")
    if not bad:
        os.makedirs(ex)
        with tarfile.open(arc, "r:gz") as tf:
            for m in tf.getmembers():
                parts = m.name.split("/")
                if m.name.startswith("/") or ".." in parts or parts[0] != name or not (m.isfile() or m.isdir()):
                    bad.append(f"member not allowed: {m.name!r}")
            if not bad:
                tf.extractall(ex, filter="data")
    if not bad:
        os.makedirs(out)
        files = sorted(f for f in os.listdir(os.path.join(ex, name)) if f.endswith(".json") or f.endswith(".log"))
        for f in files:
            shutil.copy2(os.path.join(ex, name, f), os.path.join(out, f))
        rec["files"] = {f: sha(os.path.join(out, f)) for f in files}
        n = 0
        for f in files:
            if f.endswith(".json"):
                with open(os.path.join(out, f), encoding="utf-8") as fh:
                    n += len(json.load(fh))
        rec["tasks_measured"] = n
    rec["ok"] = not bad
    with open(os.path.join(STUDY, "runs", "kaggle", f"FETCH_{name}.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1, sort_keys=True)
        f.write("\n")
    print(json.dumps({k: rec.get(k) for k in ("name", "ok", "archive_sha256", "tasks_measured", "problems")}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
