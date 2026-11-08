"""Build the private Kaggle kernels of phase 2 (after the GO; standard library only).

    python3 -I ngrow/kaggle_build.py benchmarks                kernels A (ConceptARC, Mini-ARC) and B (1D-ARC)
    python3 -I ngrow/kaggle_build.py arc2 A_OUTPUT B_OUTPUT     kernel C (ARC-AGI-2 check), after A and B finished

The route is the construction test's replay (kaggle_entries/grammar_growth_research/): the files below, at their
repository paths, are packed into a deterministic .tar.gz embedded in the notebook with its sha256; the notebook
checks the digest, unpacks, runs `python -I run.py phase2 RUN_DIR BENCHES 4` with NG_PACKAGE=1 and PYTHONHASHSEED=0,
and packs RUN_DIR into /kaggle/working/<KERNEL>_outputs.tar.gz. The package holds demonstrations and test inputs only
(never a test output). Kernels are private, CPU only, internet off. Writes runs/kaggle/PACKAGE_MANIFEST_<mode>.json
and runs/kaggle/<KERNEL>/{notebook.ipynb, kernel-metadata.json}.
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
CG = "experiments/capability_growth_20261027/cgrow/"
SW = "experiments/architecture_sweep_20261026/"
CODE = ([CG + m + ".py" for m in ("__init__", "controller", "lang0", "paths", "probes", "schema", "search",
                                  "selfext_core")]
        + [SW + "a2/" + m + ".py" for m in ("__init__", "arcdsl", "bus", "corpus", "grammars", "library")]
        + [SW + "a2/out/corpus.json"]
        + [SW + "harness/" + m + ".py" for m in ("__init__", "data", "ledger", "paths")]
        + ["outputs/search_components/resources_20261026/github/arc-dsl/" + f
           for f in ("LICENSE", "arc_types.py", "constants.py", "dsl.py", "solvers.py")]
        + [STUDY_REL + "/" + f for f in ("run.py", "PROTOCOL.md", "FREEZE.json", "config/STUDY_CONFIG.json",
                                         "split/SPLIT.json", "runs/GO_PHASE2")]
        + [STUDY_REL + "/ngrow/" + m + ".py" for m in ("__init__", "env", "data", "plugin", "gate", "controller_run",
                                                       "grow", "held", "arc2", "bench", "score", "analysis",
                                                       "phase2")])
BENCH_DATA = [(f"data/prepared/{b}/{f}", os.path.join(DATA, b, f)) for b in ("concept_arc", "mini_arc", "1d_arc")
              for f in ("real.json", "meta.json")]
ARC2_DATA = [("outputs/score_first/data/arc-agi_evaluation_challenges.json",
              os.path.join(REPO, "outputs/score_first/data/arc-agi_evaluation_challenges.json"))]
OWNER = "chimdiwalter"
KERNELS = {"A": "concept_arc,mini_arc", "B": "1d_arc", "C": "arc2"}


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


def notebook(kernel, benches, b64, digest):
    head = (f"# CORA natural-task growth test: kernel {kernel}\n\n"
            "Private research run of a pre-registered study (protocol `PROTOCOL.md` inside the package). CPU only, "
            "internet off. The package holds demonstrations and test inputs only; scoring happens elsewhere.")
    unpack = ("import base64, hashlib, io, os, subprocess, sys, tarfile\n"
              f"ARCHIVE_SHA256 = '{digest}'\n"
              f"ARCHIVE = base64.b64decode('{b64}')\n"
              "assert hashlib.sha256(ARCHIVE).hexdigest() == ARCHIVE_SHA256, 'package digest mismatch'\n"
              "ROOT = '/kaggle/working/pkg'\n"
              "with tarfile.open(fileobj=io.BytesIO(ARCHIVE), mode='r:gz') as tf:\n"
              "    tf.extractall(ROOT)\n"
              "print('package', ARCHIVE_SHA256, 'cpus', os.cpu_count())\n")
    run = (f"BENCHES = '{benches}'\n"
           f"STUDY = os.path.join(ROOT, '{STUDY_REL}')\n"
           f"RUN_DIR = os.path.join(STUDY, 'runs', 'phase2', '{kernel}')\n"
           "env = dict(os.environ, PYTHONHASHSEED='0', NG_PACKAGE='1', NG_REPO=ROOT, NG_STUDY=STUDY,\n"
           "           NG_DATA=os.path.join(ROOT, 'data', 'prepared'))\n"
           "p = subprocess.run([sys.executable, '-I', os.path.join(STUDY, 'run.py'), 'phase2', RUN_DIR, BENCHES, '4'],\n"
           "                   cwd=STUDY, env=env)\n"
           "print('return code', p.returncode)\n")
    pack = (f"out = '/kaggle/working/{kernel}_outputs.tar.gz'\n"
            "with tarfile.open(out, 'w:gz') as tf:\n"
            f"    tf.add(RUN_DIR, arcname='{kernel}')\n"
            "print(out, hashlib.sha256(open(out, 'rb').read()).hexdigest())\n"
            "print(open(os.path.join(RUN_DIR, 'STAGES.json')).read())\n")
    return {"cells": [cell("markdown", head, 1), cell("code", unpack, 2), cell("code", run, 3), cell("code", pack, 4)],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def build(mode, extra=()):
    if not os.path.exists(os.path.join(STUDY, "runs", "GO_PHASE2")):
        raise SystemExit("no GO: no package is built")
    entries = [(p, os.path.join(REPO, p)) for p in CODE] + BENCH_DATA
    kernels = ["A", "B"] if mode == "benchmarks" else ["C"]
    if mode == "arc2":
        entries += ARC2_DATA
        for kdir in extra:                     # outputs of kernels A and B: grow/ and held/ trees
            for d, _, files in os.walk(kdir):
                for f in files:
                    src = os.path.join(d, f)
                    rel = os.path.relpath(src, kdir)
                    if rel.split(os.sep)[0] in ("grow", "held") and not f.endswith(".pkl"):
                        entries.append((f"{STUDY_REL}/runs/phase2/C/{rel}", src))
    data = archive(entries)
    digest = sha_bytes(data)
    b64 = base64.b64encode(data).decode()
    man = {"archive_sha256": digest, "archive_bytes": len(data),
           "files_sha256": {rel: sha_bytes(open(src, "rb").read()) for rel, src in sorted(entries)}, "kernels": {}}
    for k in kernels:
        d = os.path.join(STUDY, "runs", "kaggle", k)
        os.makedirs(d, exist_ok=True)
        nb = json.dumps(notebook(k, KERNELS[k], b64, digest), indent=1)
        with open(os.path.join(d, "notebook.ipynb"), "w", encoding="utf-8") as f:
            f.write(nb)
        meta = {"id": f"{OWNER}/cora-natural-growth-{k.lower()}", "title": f"CORA Natural Growth {k}",
                "code_file": "notebook.ipynb", "language": "python", "kernel_type": "notebook", "is_private": True,
                "enable_gpu": False, "enable_tpu": False, "enable_internet": False, "dataset_sources": [],
                "competition_sources": [], "kernel_sources": [], "model_sources": []}
        with open(os.path.join(d, "kernel-metadata.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1)
        man["kernels"][k] = {"id": meta["id"], "benches": KERNELS[k], "notebook_sha256": sha_bytes(nb.encode())}
    with open(os.path.join(STUDY, "runs", "kaggle", f"PACKAGE_MANIFEST_{mode}.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1, sort_keys=True)
    print(json.dumps({"archive_sha256": digest, "bytes": len(data), "kernels": man["kernels"]}))


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2:])
