"""Build a private Kaggle kernel that runs the gated growth of one benchmark's SOURCE half (standard library only).

    python3 -I objgrow/kaggle_build.py BENCH [SHARDS] [--with-cache] [--tag SUFFIX]
        default 4 shards (Kaggle CPU kernels have 4 cores); --with-cache packs the benchmark's prior gate cache files
        (logs/cache/<BENCH>_gates*.pkl) so that the kernel reuses their results; --tag names a separate kernel

Same route as the natural-task growth test's kernels (ngrow/kaggle_build.py): the files below, at their repository
paths, are packed into a deterministic .tar.gz embedded in the notebook with its sha256; the notebook checks the
digest, unpacks, runs SHARDS processes of `python -I run.py grow RUN_DIR BENCH --shard i/SHARDS` with NG_PACKAGE=1,
OG_REPO, OG_STUDY, NG_REPO, NG_STUDY, NG_DATA set to the package, then `grow RUN_DIR BENCH registry`, and packs
RUN_DIR and the gate caches into /kaggle/working/<KERNEL>_outputs.tar.gz. The package holds demonstrations and test
inputs only (the benchmark's real.json and meta.json, the split, and the controller's phase 1 records of the source
half; never a test output). Kernels are private, CPU only, internet off.
Writes runs/kaggle/<KERNEL>/{notebook.ipynb, kernel-metadata.json} and runs/kaggle/PACKAGE_MANIFEST_<BENCH>.json.
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
NG_REL = "experiments/natural_growth_20261105"
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
        + [NG_REL + "/split/SPLIT.json"]
        + [NG_REL + "/feasibility/controller_source_shard" + str(i) + ".jsonl" for i in (0, 1)]
        + [NG_REL + "/ngrow/" + m + ".py" for m in ("__init__", "env", "data", "plugin")]
        + [STUDY_REL + "/run.py"]
        + [STUDY_REL + "/objgrow/" + m + ".py" for m in ("__init__", "env", "scene", "edits", "construct", "gates",
                                                         "grow")])
OWNER = "chimdiwalter"
SLUG = {"1d_arc": "1d", "concept_arc": "concept", "mini_arc": "mini"}


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


def notebook(kernel, bench, shards, b64, digest):
    head = (f"# CORA object-level growth: development run, {bench} source half\n\n"
            "Private research run (code and records inside the package). CPU only, internet off. The package holds "
            "demonstrations and test inputs only; scoring happens elsewhere.")
    unpack = ("import base64, hashlib, io, os, subprocess, sys, tarfile, time\n"
              f"ARCHIVE_SHA256 = '{digest}'\n"
              f"ARCHIVE = base64.b64decode('{b64}')\n"
              "assert hashlib.sha256(ARCHIVE).hexdigest() == ARCHIVE_SHA256, 'package digest mismatch'\n"
              "ROOT = '/kaggle/working/pkg'\n"
              "with tarfile.open(fileobj=io.BytesIO(ARCHIVE), mode='r:gz') as tf:\n"
              "    tf.extractall(ROOT)\n"
              "print('package', ARCHIVE_SHA256, 'cpus', os.cpu_count(), sys.version)\n")
    run = (f"BENCH, SHARDS = '{bench}', {shards}\n"
           f"STUDY = os.path.join(ROOT, '{STUDY_REL}')\n"
           f"NG = os.path.join(ROOT, '{NG_REL}')\n"
           f"RUN_DIR = os.path.join(STUDY, 'runs', 'kaggle_run')\n"
           "env = dict(os.environ, PYTHONHASHSEED='0', NG_PACKAGE='1', NG_REPO=ROOT, NG_STUDY=NG,\n"
           "           NG_DATA=os.path.join(ROOT, 'data', 'prepared'), OG_REPO=ROOT, OG_STUDY=STUDY)\n"
           "t0 = time.time()\n"
           "procs = [subprocess.Popen([sys.executable, '-I', os.path.join(STUDY, 'run.py'), 'grow', RUN_DIR, BENCH,\n"
           "                           '--shard', f'{i}/{SHARDS}'], cwd=STUDY, env=env) for i in range(SHARDS)]\n"
           "codes = [p.wait() for p in procs]\n"
           "print('shards', codes, 'wall_s', round(time.time() - t0))\n"
           "p = subprocess.run([sys.executable, '-I', os.path.join(STUDY, 'run.py'), 'grow', RUN_DIR, BENCH,\n"
           "                    'registry'], cwd=STUDY, env=env)\n"
           "print('registry return code', p.returncode, 'wall_s', round(time.time() - t0))\n")
    pack = (f"out = '/kaggle/working/{kernel}_outputs.tar.gz'\n"
            "with tarfile.open(out, 'w:gz') as tf:\n"
            "    tf.add(RUN_DIR, arcname='run')\n"
            "    tf.add(os.path.join(STUDY, 'logs', 'cache'), arcname='cache')\n"
            "print(out, hashlib.sha256(open(out, 'rb').read()).hexdigest())\n"
            "print(open(os.path.join(RUN_DIR, BENCH, 'registry.json')).read()[:3000])\n")
    return {"cells": [cell("markdown", head, 1), cell("code", unpack, 2), cell("code", run, 3), cell("code", pack, 4)],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def build(bench, shards=4, with_cache=False, tag=""):
    entries = [(p, os.path.join(REPO, p)) for p in CODE]
    entries += [(f"data/prepared/{bench}/{f}", os.path.join(DATA, bench, f)) for f in ("real.json", "meta.json")]
    if with_cache:
        # prior gate results of this benchmark (pure functions of operation and task), reused by the kernel
        cdir = os.path.join(STUDY, "logs", "cache")
        for k, fn in enumerate(sorted(fn for fn in os.listdir(cdir) if fn.startswith(f"{bench}_gates")
                                      and fn.endswith(".pkl"))):
            entries.append((f"{STUDY_REL}/logs/cache/{bench}_gates.prior{k}.pkl", os.path.join(cdir, fn)))
    for rel, src in entries:
        if "solutions" in rel or "held" in rel:
            raise SystemExit(f"refused: {rel}")
    data = archive(entries)
    digest = sha_bytes(data)
    b64 = base64.b64encode(data).decode()
    kernel = "OG" + SLUG[bench].upper() + tag.upper()
    d = os.path.join(STUDY, "runs", "kaggle", kernel)
    os.makedirs(d, exist_ok=True)
    nb = json.dumps(notebook(kernel, bench, shards, b64, digest), indent=1)
    with open(os.path.join(d, "notebook.ipynb"), "w", encoding="utf-8") as f:
        f.write(nb)
    meta = {"id": f"{OWNER}/cora-object-growth-{SLUG[bench]}{tag}", "title": f"CORA Object Growth {SLUG[bench]}{tag}",
            "code_file": "notebook.ipynb", "language": "python", "kernel_type": "notebook", "is_private": True,
            "enable_gpu": False, "enable_tpu": False, "enable_internet": False, "dataset_sources": [],
            "competition_sources": [], "kernel_sources": [], "model_sources": []}
    with open(os.path.join(d, "kernel-metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    man = {"bench": bench, "shards": shards, "archive_sha256": digest, "archive_bytes": len(data),
           "files_sha256": {rel: sha_bytes(open(src, "rb").read()) for rel, src in sorted(entries)},
           "kernel": {"id": meta["id"], "notebook_sha256": sha_bytes(nb.encode())}}
    with open(os.path.join(STUDY, "runs", "kaggle", f"PACKAGE_MANIFEST_{bench}{tag}.json"), "w",
              encoding="utf-8") as f:
        json.dump(man, f, indent=1, sort_keys=True)
    with open(os.path.join(d, "package.tar.gz"), "wb") as f:
        f.write(data)
    print(json.dumps({"kernel": meta["id"], "archive_sha256": digest, "bytes": len(data)}))


if __name__ == "__main__":
    # BENCH [SHARDS] [--with-cache] [--tag SUFFIX]
    args = sys.argv[1:]
    bench = args[0]
    shards = int(args[1]) if len(args) > 1 and args[1].isdigit() else 4
    build(bench, shards, with_cache="--with-cache" in args,
          tag=args[args.index("--tag") + 1] if "--tag" in args else "")
