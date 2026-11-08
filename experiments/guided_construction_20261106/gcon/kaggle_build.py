"""Build the private Kaggle CPU kernels of the held run (standard library only; PROTOCOL.md section 7).

    python3 -s -B gcon/kaggle_build.py candidate     the package without the GO (reviewed bytes; smoke test)
    python3 -s -B gcon/kaggle_build.py final         after the GO: the same files plus runs/GO; refused unless the GO
                                                     names this protocol and this freeze and every other file equals
                                                     the candidate manifest

One package for the three kernels (the files below at their repository paths, a deterministic .tar.gz embedded in
each notebook with its sha256): GC1D runs the 1D-ARC held half, GCCM the ConceptARC then the Mini-ARC held half,
GCARC2 the ARC-AGI-2 public evaluation. Each kernel unpacks, checks the digest, runs 4 worker processes per set
(`python -s -B run.py held RUN_DIR SET i/4`, PYTHONHASHSEED=0), stops the workers after 7.5 hours of wall time (30
CPU-h for 4 workers), and packs RUN_DIR into /kaggle/working/<KERNEL>_outputs.tar.gz. The package holds
demonstrations and test inputs only: the benchmarks' real.json and meta.json, the split, the ARC-AGI-2 evaluation
challenges; never a solution file. Kernels are private, CPU only, internet off.
Writes runs/kaggle/<KERNEL>/{notebook.ipynb, kernel-metadata.json}, runs/kaggle/package_<mode>.tar.gz and
runs/kaggle/PACKAGE_MANIFEST_<mode>.json.
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
STUDY_REL = os.path.relpath(STUDY, REPO)
DATA = "/path/to/benchmark_data/prepared"
NG = "experiments/natural_growth_20261105/"
NGB = "experiments/natural_growth_b_20261105/"
OG = "experiments/object_growth_20261105/"
CG = "experiments/capability_growth_20261027/cgrow/"
SW = "experiments/architecture_sweep_20261026/"
CODE = ([CG + m + ".py" for m in ("__init__", "controller", "lang0", "paths", "probes", "schema", "search",
                                  "selfext_core")]
        + [SW + "a2/" + m + ".py" for m in ("__init__", "arcdsl", "bus", "corpus", "grammars", "library")]
        + [SW + "a2/out/corpus.json"]
        + [SW + "harness/" + m + ".py" for m in ("__init__", "data", "ledger", "paths")]
        + ["outputs/search_components/resources_20261026/github/arc-dsl/" + f
           for f in ("LICENSE", "arc_types.py", "constants.py", "dsl.py", "solvers.py")]
        + [NG + "split/SPLIT.json"]
        + [NG + "ngrow/" + m + ".py" for m in ("__init__", "env", "data", "plugin", "score", "gate", "analysis")]
        + [NGB + "ngb/" + m + ".py" for m in ("__init__", "env", "gate", "ops", "object_arm")]
        + [OG + "objgrow/" + m + ".py" for m in ("__init__", "env", "scene", "edits", "construct", "gates", "grow",
                                                 "arm")]
        + [STUDY_REL + "/" + p for p in ("run.py", "PROTOCOL.md", "FREEZE.json", "config/CONFIG.json",
                                         "models/full.json", "models/lobo_1d_arc.json", "models/lobo_concept_arc.json",
                                         "models/lobo_mini_arc.json", "launch/kernel_run.py")]
        + [STUDY_REL + "/gcon/" + m + ".py" for m in ("__init__", "env", "engine", "features", "model", "policy",
                                                     "units", "held", "gate")])
DATA_FILES = [(f"data/prepared/{b}/{f}", os.path.join(DATA, b, f)) for b in ("1d_arc", "concept_arc", "mini_arc")
              for f in ("real.json", "meta.json")]
ARC2 = ("outputs/score_first/data/arc-agi_evaluation_challenges.json",
        os.path.join(REPO, "outputs/score_first/data/arc-agi_evaluation_challenges.json"))
OWNER = "chimdiwalter"
KERNELS = {"GC1D": ("1d", ["1d_arc"]), "GCCM": ("cm", ["concept_arc", "mini_arc"]), "GCARC2": ("arc2", ["arc2"])}
WORKERS = 4
WALL_LIMIT_S = int(7.5 * 3600)


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def archive(entries):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tf:
            for rel, src in sorted(entries):
                data = open(src, "rb").read()
                ti = tarfile.TarInfo(rel)
                ti.size, ti.mtime, ti.mode, ti.uid, ti.gid, ti.uname, ti.gname = len(data), 0, 0o644, 0, 0, "", ""
                tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def cell(kind, src, n):
    c = {"cell_type": kind, "id": f"cell-{n}", "metadata": {}, "source": src}
    if kind == "code":
        c.update(execution_count=None, outputs=[])
    return c


def notebook(kernel, sets, b64, digest):
    head = (f"# CORA guided construction: held run ({', '.join(sets)})\n\n"
            "Private research run (code and records inside the package). CPU only, internet off. The package holds "
            "demonstrations and test inputs only; scoring happens elsewhere, once.")
    unpack = ("import base64, hashlib, io, os, subprocess, sys, tarfile, time\n"
              f"ARCHIVE_SHA256 = '{digest}'\n"
              f"ARCHIVE = base64.b64decode('{b64}')\n"
              "assert hashlib.sha256(ARCHIVE).hexdigest() == ARCHIVE_SHA256, 'package digest mismatch'\n"
              "ROOT = '/kaggle/working/pkg'\n"
              "with tarfile.open(fileobj=io.BytesIO(ARCHIVE), mode='r:gz') as tf:\n"
              "    tf.extractall(ROOT)\n"
              "print('package', ARCHIVE_SHA256, 'cpus', os.cpu_count(), sys.version)\n")
    run = (f"SETS = {sets!r}\n"
           f"STUDY = os.path.join(ROOT, '{STUDY_REL}')\n"
           "RUN_DIR = os.path.join(STUDY, 'runs', 'held_run')\n"
           f"p = subprocess.run([sys.executable, '-s', '-B', os.path.join(STUDY, 'launch', 'kernel_run.py'), ROOT,\n"
           f"                    RUN_DIR, '{WORKERS}', '{WALL_LIMIT_S}'] + SETS)\n"
           "print('kernel_run return code', p.returncode)\n")
    pack = (f"out = '/kaggle/working/{kernel}_outputs.tar.gz'\n"
            "with tarfile.open(out, 'w:gz') as tf:\n"
            "    tf.add(RUN_DIR, arcname='run')\n"
            "print(out, hashlib.sha256(open(out, 'rb').read()).hexdigest())\n")
    return {"cells": [cell("markdown", head, 1), cell("code", unpack, 2), cell("code", run, 3), cell("code", pack, 4)],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def entries(mode):
    out = [(p, os.path.join(REPO, p)) for p in CODE] + DATA_FILES + [ARC2]
    if mode == "final":
        out.append((STUDY_REL + "/runs/GO", os.path.join(STUDY, "runs", "GO")))
    for rel, _ in out:
        if "solutions" in rel:
            raise SystemExit(f"refused: {rel}")
    return out


def build(mode):
    if mode not in ("candidate", "final"):
        raise SystemExit("mode is candidate or final")
    ents = entries(mode)
    files = {rel: sha_bytes(open(src, "rb").read()) for rel, src in sorted(ents)}
    kdir = os.path.join(STUDY, "runs", "kaggle")
    os.makedirs(kdir, exist_ok=True)
    if mode == "final":
        cand = json.load(open(os.path.join(kdir, "PACKAGE_MANIFEST_candidate.json"), encoding="utf-8"))
        diff = sorted(k for k in set(cand["files_sha256"]) | set(files)
                      if k != STUDY_REL + "/runs/GO" and cand["files_sha256"].get(k) != files.get(k))
        if diff:
            raise SystemExit("files differ from the candidate manifest: " + ", ".join(diff))
        go = open(os.path.join(STUDY, "runs", "GO"), encoding="utf-8").read().splitlines()
        want = [f"protocol_sha256 {files[STUDY_REL + '/PROTOCOL.md']}",
                f"freeze_sha256 {files[STUDY_REL + '/FREEZE.json']}"]
        if go[:2] != want:
            raise SystemExit("runs/GO does not name this protocol and this freeze")
    data = archive(ents)
    digest = sha_bytes(data)
    b64 = base64.b64encode(data).decode()
    with open(os.path.join(kdir, f"package_{mode}.tar.gz"), "wb") as f:
        f.write(data)
    man = {"mode": mode, "archive_sha256": digest, "archive_bytes": len(data), "files_sha256": files, "kernels": {}}
    for kernel, (slug, sets) in KERNELS.items():
        d = os.path.join(kdir, kernel + ("" if mode == "final" else "_candidate"))
        os.makedirs(d, exist_ok=True)
        nb = json.dumps(notebook(kernel, sets, b64, digest), indent=1)
        with open(os.path.join(d, "notebook.ipynb"), "w", encoding="utf-8") as f:
            f.write(nb)
        meta = {"id": f"{OWNER}/cora-guided-construction-{slug}", "title": f"CORA Guided Construction {slug}",
                "code_file": "notebook.ipynb", "language": "python", "kernel_type": "notebook", "is_private": True,
                "enable_gpu": False, "enable_tpu": False, "enable_internet": False, "dataset_sources": [],
                "competition_sources": [], "kernel_sources": [], "model_sources": []}
        with open(os.path.join(d, "kernel-metadata.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1)
        man["kernels"][kernel] = {"id": meta["id"], "sets": sets, "notebook_sha256": sha_bytes(nb.encode()),
                                  "metadata_sha256": sha_bytes(open(os.path.join(d, "kernel-metadata.json"),
                                                                    "rb").read())}
    with open(os.path.join(kdir, f"PACKAGE_MANIFEST_{mode}.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1, sort_keys=True)
    print(json.dumps({"mode": mode, "archive_sha256": digest, "bytes": len(data),
                      "kernels": {k: v["notebook_sha256"] for k, v in man["kernels"].items()}}))


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "candidate")
