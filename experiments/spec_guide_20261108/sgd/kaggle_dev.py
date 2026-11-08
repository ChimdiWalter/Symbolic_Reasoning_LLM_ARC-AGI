"""Build private Kaggle CPU kernels that generate development data (development pool, training or validation
families only; never a held family or a held-pool grid). Standard library only.

    python3 -s -B sgd/kaggle_dev.py NAME WALL_LIMIT_S JOB [JOB ...]       JOB = "kind|out|partition|n|seed"
"""
import base64
import gzip
import hashlib
import io
import json
import os
import sys
import tarfile

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(STUDY))
REL = os.path.relpath(STUDY, REPO)
sys.path.insert(0, os.path.join(REPO, "experiments", "guided_construction_20261106", "gcon"))
import kaggle_build as GKB                                                          # noqa: E402

GC = "experiments/guided_construction_20261106/"
CODE = ([p for p in GKB.CODE if not p.startswith(GC) and "/ngb/" not in p]
        + [GC + "gcon/" + m + ".py" for m in ("__init__", "env", "engine", "features")]
        + [REL + "/run.py", REL + "/launch/devgen_run.py"]
        + [REL + "/sgd/" + m + ".py" for m in ("__init__", "env", "gen")]
        + ["outputs/score_first/data/arc-agi_training_challenges.json"])
OWNER = "chimdiwalter"


def build(name, limit, jobs):
    for j in jobs:
        kind, out, part, n, seed = j.split("|")
        if part not in ("train", "val") or kind not in ("cheap", "traced"):
            raise SystemExit(f"refused job {j}")
    ents = [(p, os.path.join(REPO, p)) for p in CODE]
    for rel, _ in ents:
        if "solutions" in rel or "evaluation" in rel:
            raise SystemExit(f"refused: {rel}")
    data = GKB.archive(ents)
    digest = hashlib.sha256(data).hexdigest()
    b64 = base64.b64encode(data).decode()
    kernel = f"SGDEV{name.upper()}"
    d = os.path.join(STUDY, "runs", "kaggle_dev", kernel)
    os.makedirs(d, exist_ok=True)
    head = ("# CORA specification-reading guide: development data generation\n\nPrivate research run; CPU only, "
            "internet off. Development pool and training or validation families only.")
    unpack = ("import base64, hashlib, io, os, subprocess, sys, tarfile, time\n"
              f"ARCHIVE_SHA256 = '{digest}'\n"
              f"ARCHIVE = base64.b64decode('{b64}')\n"
              "assert hashlib.sha256(ARCHIVE).hexdigest() == ARCHIVE_SHA256, 'package digest mismatch'\n"
              "ROOT = '/kaggle/working/pkg'\n"
              "with tarfile.open(fileobj=io.BytesIO(ARCHIVE), mode='r:gz') as tf:\n"
              "    tf.extractall(ROOT)\n"
              "print('package', ARCHIVE_SHA256, 'cpus', os.cpu_count(), sys.version)\n")
    run = (f"STUDY = os.path.join(ROOT, '{REL}')\n"
           f"JOBS = {jobs!r}\n"
           f"p = subprocess.run([sys.executable, '-s', '-B', os.path.join(STUDY, 'launch', 'devgen_run.py'), ROOT, "
           f"'{limit}'] + JOBS)\n"
           "print('return code', p.returncode)\n")
    pack = (f"out = '/kaggle/working/{kernel}_outputs.tar.gz'\n"
            "with tarfile.open(out, 'w:gz') as tf:\n"
            "    tf.add(os.path.join(STUDY, 'dev'), arcname='dev')\n"
            "print(out, hashlib.sha256(open(out, 'rb').read()).hexdigest())\n")
    cells = [GKB.cell("markdown", head, 1), GKB.cell("code", unpack, 2), GKB.cell("code", run, 3),
             GKB.cell("code", pack, 4)]
    nb = json.dumps({"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                                                 "name": "python3"},
                                                  "language_info": {"name": "python"}},
                     "nbformat": 4, "nbformat_minor": 5}, indent=1)
    with open(os.path.join(d, "notebook.ipynb"), "w", encoding="utf-8") as f:
        f.write(nb)
    meta = {"id": f"{OWNER}/cora-spec-guide-devgen-{name.lower()}", "title": f"CORA Spec Guide Devgen {name}",
            "code_file": "notebook.ipynb", "language": "python", "kernel_type": "notebook", "is_private": True,
            "enable_gpu": False, "enable_tpu": False, "enable_internet": False, "dataset_sources": [],
            "competition_sources": [], "kernel_sources": [], "model_sources": []}
    with open(os.path.join(d, "kernel-metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    print(json.dumps({"kernel": meta["id"], "archive_sha256": digest, "bytes": len(data), "dir": d}))


if __name__ == "__main__":
    build(sys.argv[1], int(sys.argv[2]), sys.argv[3:])
