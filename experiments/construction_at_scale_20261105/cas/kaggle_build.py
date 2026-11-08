"""Build the private Kaggle kernels of phase 2 (one per world), after generation and the GO gate.

    python3 -I cas/kaggle_build.py            (standard library only; run from anywhere)

The route is the S1 replay's (kaggle_entries/grammar_growth_research/build_notebook.py): the files below, at their
repository paths, are packed into a deterministic .tar.gz that is embedded in the notebook with its sha256; the
notebook checks the digest, unpacks, and runs `python -m cas.kaggle_main WORLD WORLD_DIR` with PYTHONHASHSEED=0 and
CAS_PACK_DIR=/kaggle/working, so WORLD_DIR/runs is packed to /kaggle/working/<WORLD>_outputs.tar.gz after every
stage (and once more at the end). Kernels are private, CPU only, internet off.
Writes runs/kaggle/PACKAGE_MANIFEST.json and runs/kaggle/<WORLD>/{notebook.ipynb, kernel-metadata.json}.
"""
import base64
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(STUDY))
STUDY_REL = os.path.relpath(STUDY, REPO)
S1 = "experiments/capability_growth_20261027/cgrow/"
SW = "experiments/architecture_sweep_20261026/"
FILES = ([S1 + m + ".py" for m in ("__init__", "controller", "episode", "evaluate", "experiment", "invent", "lang0",
                                   "naming", "paths", "probes", "prompts", "registry", "s1", "schema", "search",
                                   "testib", "testib_rest")]
         + [SW + "a2/" + m + ".py" for m in ("__init__", "arcdsl", "bus", "corpus", "grammars", "library")]
         + [SW + "a2/out/corpus.json"]
         + [SW + "harness/" + m + ".py" for m in ("__init__", "data", "ledger", "paths")]
         + ["experiments/cora_cast_20261026/cast/" + m + ".py" for m in ("__init__", "absdom", "contract_check")]
         + ["outputs/search_components/resources_20261026/github/arc-dsl/" + f
            for f in ("LICENSE", "arc_types.py", "constants.py", "dsl.py", "solvers.py")]
         + [STUDY_REL + "/cas/" + m + ".py" for m in ("__init__", "env", "run_world", "kaggle_main", "analysis", "bench")]
         + [STUDY_REL + "/" + f for f in ("PROTOCOL.md", "FREEZE.json", "config/STUDY_CONFIG.json")])
WORLD_FILES = ("partitions/TASKS_SYSTEM.json", "partitions/PARTITIONS_MANIFEST.json", "evaluator_only/TASKS_EVAL.json",
               "evaluator_only/REMOVED.json")
OWNER = "chimdiwalter"


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def archive(paths):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tf:
            for rel in sorted(paths):
                data = open(os.path.join(REPO, rel), "rb").read()
                ti = tarfile.TarInfo(rel)
                ti.size, ti.mtime, ti.mode, ti.uid, ti.gid, ti.uname, ti.gname = len(data), 0, 0o644, 0, 0, "", ""
                tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def cell(kind, src, n):
    c = {"cell_type": kind, "id": f"cell-{n}", "metadata": {}, "source": src}
    if kind == "code":
        c.update(execution_count=None, outputs=[])
    return c


def notebook(world, b64, digest):
    head = (f"# CORA construction test at scale: world {world}\n\n"
            "Private research run of a pre-registered study (protocol `PROTOCOL.md` inside the package). CPU only, "
            "internet off. The tasks are built from ARC training input grids; they measure a mechanism, not ARC "
            "accuracy. The code is the frozen construction test of the CORA project, run unchanged.")
    unpack = ("import base64, hashlib, io, os, subprocess, sys, tarfile\n"
              f"ARCHIVE_SHA256 = '{digest}'\n"
              f"ARCHIVE = base64.b64decode('{b64}')\n"
              "assert hashlib.sha256(ARCHIVE).hexdigest() == ARCHIVE_SHA256, 'package digest mismatch'\n"
              "ROOT = '/kaggle/working/pkg'\n"
              "with tarfile.open(fileobj=io.BytesIO(ARCHIVE), mode='r:gz') as tf:\n"
              "    tf.extractall(ROOT)\n"
              "print('package', ARCHIVE_SHA256, 'cpus', os.cpu_count())\n")
    run = (f"WORLD = '{world}'\n"
           f"STUDY = os.path.join(ROOT, '{STUDY_REL}')\n"
           "WD = os.path.join(STUDY, 'runs', 'generated', WORLD)\n"
           "env = dict(os.environ, PYTHONHASHSEED='0', CAS_PACKAGE='1', CAS_REPO=ROOT, CAS_STUDY=STUDY, "
           "CAS_PACK_DIR='/kaggle/working', CAS_ARCHIVE_SHA256=ARCHIVE_SHA256)\n"
           "p = subprocess.run([sys.executable, '-m', 'cas.kaggle_main', WORLD, WD], cwd=STUDY, env=env)\n"
           "print('return code', p.returncode)\n")
    pack = ("out = f'/kaggle/working/{WORLD}_outputs.tar.gz'\n"
            "with tarfile.open(out, 'w:gz') as tf:\n"
            "    tf.add(os.path.join(WD, 'runs'), arcname=f'{WORLD}/runs')\n"
            "print(out, hashlib.sha256(open(out, 'rb').read()).hexdigest())\n"
            "print(open(os.path.join(WD, 'runs', 'STAGES.json')).read())\n")
    return {"cells": [cell("markdown", head, 1), cell("code", unpack, 2), cell("code", run, 3), cell("code", pack, 4)],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def main():
    gate = subprocess.run([sys.executable, "-I", os.path.join(STUDY, "cas", "gate.py"), "package"],
                          capture_output=True, text=True)
    print(gate.stdout.strip())
    if gate.returncode != 0:
        raise SystemExit("gate refused: no package is built")
    cfg = json.load(open(os.path.join(STUDY, "config", "STUDY_CONFIG.json"), encoding="utf-8"))
    # the analysis directory arguments: exactly one committed world folder per configured world, each complete
    world_dirs = [f"runs/generated/{w}" for w in cfg["world_order"]]
    for w, d in zip(cfg["world_order"], world_dirs):
        for f in WORLD_FILES:
            if not os.path.exists(os.path.join(STUDY, d, f)):
                raise SystemExit(f"world {w}: {f} missing in {d}")
        man = json.load(open(os.path.join(STUDY, d, "partitions", "PARTITIONS_MANIFEST.json"), encoding="utf-8"))
        if man.get("world") != w:
            raise SystemExit(f"world {w}: manifest names {man.get('world')!r}")
    if len(set(world_dirs)) != len(cfg["world_order"]):
        raise SystemExit("duplicate world in the configuration")
    paths = list(FILES) + [f"{STUDY_REL}/runs/generated/{w}/{f}" for w in cfg["world_order"] for f in WORLD_FILES]
    data = archive(paths)
    digest = sha_bytes(data)
    b64 = base64.b64encode(data).decode()
    man = {"archive_sha256": digest, "archive_bytes": len(data), "analysis_world_dirs": world_dirs,
           "files_sha256": {p: sha_bytes(open(os.path.join(REPO, p), "rb").read()) for p in sorted(paths)},
           "kernels": {}}
    for w in cfg["world_order"]:
        d = os.path.join(STUDY, "runs", "kaggle", w)
        os.makedirs(d, exist_ok=True)
        nb = json.dumps(notebook(w, b64, digest), indent=1)
        with open(os.path.join(d, "notebook.ipynb"), "w", encoding="utf-8") as f:
            f.write(nb)
        meta = {"id": f"{OWNER}/cora-construction-at-scale-{w.lower()}", "title": f"CORA Construction At Scale {w}",
                "code_file": "notebook.ipynb", "language": "python", "kernel_type": "notebook", "is_private": True,
                "enable_gpu": False, "enable_tpu": False, "enable_internet": False, "dataset_sources": [],
                "competition_sources": [], "kernel_sources": [], "model_sources": []}
        with open(os.path.join(d, "kernel-metadata.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1)
        man["kernels"][w] = {"id": meta["id"], "notebook_sha256": sha_bytes(nb.encode())}
    with open(os.path.join(STUDY, "runs", "kaggle", "PACKAGE_MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1, sort_keys=True)
    print(json.dumps({"archive_sha256": digest, "bytes": len(data), "kernels": man["kernels"]}))


if __name__ == "__main__":
    main()
