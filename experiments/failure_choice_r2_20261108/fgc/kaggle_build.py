"""Build one private Kaggle CPU kernel that measures a list of tasks (fgc/measure.py), several processes at once.

    python3 -I fgc/kaggle_build.py NAME TASKS_SYSTEM_REL PROCESSES WORLD:ID[,ID...] [WORLD:ID,...]

The package is the construction test's kernel route: the files below at their repository paths, packed into a
deterministic .tar.gz embedded in the notebook with its sha256; the notebook checks the digest, unpacks into /tmp,
runs `python -m fgc.measure WORLD TASKS OUT IDS...` in PROCESSES parallel processes (each a fixed share of the
tasks, PYTHONHASHSEED=0, CAS_PACKAGE=1), then packs the measurement files into /kaggle/working/NAME_outputs.tar.gz
and prints its sha256. Every cost is counted in calls, so the machine does not change any measured value except
the CPU seconds recorded beside it. Only system-side files are packed: task demonstrations and query inputs, the
worlds' grammars (removed sets) and controller records; never a label, a cause or a family.
Writes runs/kaggle/NAME/{notebook.ipynb, kernel-metadata.json, PACKAGE.json}. Kernels are private, CPU only,
internet off.
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
CAS_REL = "experiments/construction_at_scale_20261105"
S1 = "experiments/capability_growth_20261027/cgrow/"
SW = "experiments/architecture_sweep_20261026/"
FILES = ([S1 + m + ".py" for m in ("__init__", "controller", "episode", "evaluate", "experiment", "invent", "lang0",
                                   "naming", "paths", "probes", "prompts", "registry", "s1", "schema", "search",
                                   "testib", "testib_rest", "tasks")]
         + [SW + "a2/" + m + ".py" for m in ("__init__", "arcdsl", "bus", "corpus", "grammars", "library")]
         + [SW + "a2/out/corpus.json"]
         + [SW + "harness/" + m + ".py" for m in ("__init__", "data", "ledger", "paths")]
         + ["experiments/cora_cast_20261026/cast/" + m + ".py" for m in ("__init__", "absdom", "contract_check")]
         + ["outputs/search_components/resources_20261026/github/arc-dsl/" + f
            for f in ("LICENSE", "arc_types.py", "constants.py", "dsl.py", "solvers.py")]
         + [CAS_REL + "/cas/" + m + ".py" for m in ("__init__", "env")]
         + [STUDY_REL + "/fgc/" + m + ".py" for m in ("__init__", "common", "measure", "views")]
         + [STUDY_REL + "/config/STUDY_CONFIG.json"]
         + [f"{STUDY_REL}/runs/worlds/{w}/{f}" for w in ("W1", "W2", "W3")
            for f in ("partitions/TASKS_SYSTEM.json", "evaluator_only/REMOVED.json", "runs/prep_v4/records.pkl")])
OWNER = "chimdiwalter"
GEN_FILES = ([CAS_REL + "/cas/generate.py", STUDY_REL + "/fgc/generate.py", STUDY_REL + "/fgc/views.py",
              STUDY_REL + "/fgc/kaggle_gen_main.py", STUDY_REL + "/config/POOLS.json",
              STUDY_REL + "/runs/source/SOURCE_SYSTEM_R1.json",
              STUDY_REL + "/runs/source/evaluator_only/SOURCE_EVAL_R1.json"]
             + [f"{STUDY_REL}/runs/worlds/{w}/evaluator_only/TASKS_EVAL.json" for w in ("W1", "W2", "W3")])
ARC_TRAIN = "<ARC data folder>/arc-agi_training_challenges.json"


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def archive(paths, extra=None):
    """extra: {archive path: absolute source path} for files outside the repository (the ARC data file)."""
    buf = io.BytesIO()
    extra = extra or {}
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tf:
            for rel in sorted(list(paths) + list(extra)):
                data = open(extra.get(rel) or os.path.join(REPO, rel), "rb").read()
                ti = tarfile.TarInfo(rel)
                ti.size, ti.mtime, ti.mode, ti.uid, ti.gid, ti.uname, ti.gname = len(data), 0, 0o644, 0, 0, "", ""
                tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def cell(kind, src, n):
    c = {"cell_type": kind, "id": f"cell-{n}", "metadata": {}, "source": src}
    if kind == "code":
        c.update(execution_count=None, outputs=[])
    return c


def notebook(name, b64, digest, tasks_rel, shares, mode=""):
    head = (f"# CORA failure-guided choice test: measurement {name}\n\n"
            "Private research run (CPU only, internet off). Tasks are built from ARC training input grids; they "
            "measure a mechanism, not ARC accuracy. Each task's base search, failure record, deeper search and "
            "typed-hole construction are measured once, in counted primitive executions.")
    unpack = ("import base64, hashlib, io, json, os, subprocess, sys, tarfile, time\n"
              f"ARCHIVE_SHA256 = '{digest}'\n"
              f"ARCHIVE = base64.b64decode('{b64}')\n"
              "assert hashlib.sha256(ARCHIVE).hexdigest() == ARCHIVE_SHA256, 'package digest mismatch'\n"
              "ROOT = '/tmp/pkg'\n"
              "with tarfile.open(fileobj=io.BytesIO(ARCHIVE), mode='r:gz') as tf:\n"
              "    tf.extractall(ROOT)\n"
              "print('package', ARCHIVE_SHA256, 'cpus', os.cpu_count())\n")
    run = (f"NAME = '{name}'\n"
           f"STUDY = os.path.join(ROOT, '{STUDY_REL}')\n"
           f"TASKS = os.path.join(STUDY, '{tasks_rel}')\n"
           f"SHARES = {json.dumps(shares)}\n"
           "OUT = os.path.join(STUDY, 'runs', 'measure', NAME)\n"
           "os.makedirs(OUT, exist_ok=True)\n"
           "env = dict(os.environ, PYTHONHASHSEED='0', CAS_PACKAGE='1', CAS_REPO=ROOT, CAS_STUDY=STUDY, "
           "PYTHONPATH=STUDY)\n"
           "procs = []\n"
           "for k, share in enumerate(SHARES):\n"
           "    log = open(os.path.join(OUT, f'share_{k}.log'), 'w')\n"
           f"    MODE = '{mode}'\n"
           "    cmd = ' ; '.join(f'{sys.executable} -m fgc.measure {MODE} {w} {TASKS} {OUT}/share_{k}_{w}.json ' + ' '.join(ids)"
           " for w, ids in share)\n"
           "    procs.append(subprocess.Popen(['sh', '-c', cmd], cwd=STUDY, env=env, stdout=log, stderr=log))\n"
           "t0 = time.time()\n"
           "rcs = [p.wait() for p in procs]\n"
           "print('return codes', rcs, 'wall_s', round(time.time() - t0, 1))\n")
    pack = ("out = f'/kaggle/working/{NAME}_outputs.tar.gz'\n"
            "with tarfile.open(out, 'w:gz') as tf:\n"
            "    tf.add(OUT, arcname=f'{NAME}')\n"
            "print(out, hashlib.sha256(open(out, 'rb').read()).hexdigest())\n")
    return {"cells": [cell("markdown", head, 1), cell("code", unpack, 2), cell("code", run, 3), cell("code", pack, 4)],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def main(name, tasks_rel, processes, specs, mode=""):
    tasks = json.load(open(os.path.join(STUDY, tasks_rel)))
    items = []
    for spec in specs:
        w, ids = spec.split(":", 1)
        for i in ids.split(","):
            if i not in tasks:
                raise SystemExit(f"task {i} not in {tasks_rel}")
            items.append((w, i))
    shares = [[] for _ in range(int(processes))]
    for k, (w, i) in enumerate(items):                      # round robin, then grouped by world within a share
        shares[k % len(shares)].append((w, i))
    grouped = []
    for sh in shares:
        by = {}
        for w, i in sh:
            by.setdefault(w, []).append(i)
        grouped.append([[w, by[w]] for w in sorted(by)])
    paths = list(FILES) + [f"{STUDY_REL}/{tasks_rel}"]
    data = archive(paths)
    digest = sha_bytes(data)
    d = os.path.join(STUDY, "runs", "kaggle", name)
    os.makedirs(d, exist_ok=True)
    nb = json.dumps(notebook(name, base64.b64encode(data).decode(), digest, tasks_rel, grouped, mode), indent=1)
    with open(os.path.join(d, "notebook.ipynb"), "w", encoding="utf-8") as f:
        f.write(nb)
    meta = {"id": f"{OWNER}/cora-failure-choice-{name.lower().replace('_', '-')}",
            "title": f"CORA Failure Choice {name.replace('_', ' ')}", "code_file": "notebook.ipynb",
            "language": "python", "kernel_type": "notebook", "is_private": True, "enable_gpu": False,
            "enable_tpu": False, "enable_internet": False, "dataset_sources": [], "competition_sources": [],
            "kernel_sources": [], "model_sources": []}
    with open(os.path.join(d, "kernel-metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    man = {"archive_sha256": digest, "archive_bytes": len(data), "notebook_sha256": sha_bytes(nb.encode()),
           "files_sha256": {p: sha_bytes(open(os.path.join(REPO, p), "rb").read()) for p in sorted(paths)},
           "tasks": len(items), "shares": grouped, "kernel": meta["id"]}
    with open(os.path.join(d, "PACKAGE.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1, sort_keys=True)
    print(json.dumps({"kernel": meta["id"], "archive_sha256": digest, "bytes": len(data), "tasks": len(items)}))


def gen_notebook(name, b64, digest, worlds, cmd="source_world", salt="", outrel="runs/source/parts"):
    head = (f"# CORA failure-guided choice test, revision 2: source generation {name}\n\n"
            "Private research run (CPU only, internet off). Builds source tasks from ARC training input grids.")
    unpack = ("import base64, hashlib, io, json, os, subprocess, sys, tarfile, time\n"
              f"ARCHIVE_SHA256 = '{digest}'\n"
              f"ARCHIVE = base64.b64decode('{b64}')\n"
              "assert hashlib.sha256(ARCHIVE).hexdigest() == ARCHIVE_SHA256, 'package digest mismatch'\n"
              "ROOT = '/tmp/pkg'\n"
              "with tarfile.open(fileobj=io.BytesIO(ARCHIVE), mode='r:gz') as tf:\n"
              "    tf.extractall(ROOT)\n"
              "print('package', ARCHIVE_SHA256, 'cpus', os.cpu_count())\n")
    run = (f"NAME = '{name}'\n"
           f"STUDY = os.path.join(ROOT, '{STUDY_REL}')\n"
           f"WORLDS = {json.dumps(worlds)}\n"
           f"OUT = os.path.join(STUDY, '{outrel}')\n"
           f"CMD, SALT = '{cmd}', '{salt}'\n"
           "os.makedirs(OUT, exist_ok=True)\n"
           "env = dict(os.environ, PYTHONHASHSEED='0', CAS_PACKAGE='1', CAS_REPO=ROOT, CAS_STUDY=STUDY, "
           "PYTHONPATH=STUDY)\n"
           "procs = [subprocess.Popen([sys.executable, '-m', 'fgc.kaggle_gen_main', CMD, w] + ([SALT] if SALT else []), cwd=STUDY, "
           "env=env, stdout=open(os.path.join(OUT, f'gen_{w}.log'), 'w'), stderr=subprocess.STDOUT) for w in WORLDS]\n"
           "t0 = time.time()\n"
           "print('return codes', [p.wait() for p in procs], 'wall_s', round(time.time() - t0, 1))\n")
    pack = ("out = f'/kaggle/working/{NAME}_outputs.tar.gz'\n"
            "with tarfile.open(out, 'w:gz') as tf:\n"
            "    tf.add(OUT, arcname=f'{NAME}')\n"
            "print(out, hashlib.sha256(open(out, 'rb').read()).hexdigest())\n")
    return {"cells": [cell("markdown", head, 1), cell("code", unpack, 2), cell("code", run, 3), cell("code", pack, 4)],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def main_generate(name, worlds, test=False):
    paths = list(FILES) + GEN_FILES
    cmd, salt, outrel = "source_world", "", "runs/source/parts"
    if test:
        # after this revision's GO: the claim was written locally by the gate's generate stage; the salt is the
        # GO's (fgc/gate.py claim_and_salt rule), and the package carries every set whose sources are excluded
        go = os.path.join(STUDY, "GO_FGC")
        claim = json.load(open(os.path.join(STUDY, "runs", "RUN_CLAIM.json")))
        if claim.get("go_sha256") != sha_bytes(open(go, "rb").read()):
            raise SystemExit("the claim does not name this GO")
        if os.path.exists(os.path.join(STUDY, "runs", "test")):
            raise SystemExit("runs/test/ exists already")
        cmd, salt, outrel = "test_world", "fgc2-test-" + sha_bytes(open(go, "rb").read())[:16], "runs/test_parts"
        r1 = os.path.relpath(os.path.join(os.path.dirname(STUDY), "failure_choice_20261108"), REPO)
        paths += [STUDY_REL + "/runs/source/evaluator_only/SOURCE_EVAL.json",
                  r1 + "/runs/test/evaluator_only/TEST_EVAL.json"]
    extra = {"data_arc/arc-agi_training_challenges.json": ARC_TRAIN}
    data = archive(paths, extra)
    digest = sha_bytes(data)
    d = os.path.join(STUDY, "runs", "kaggle", name)
    os.makedirs(d, exist_ok=True)
    nb = json.dumps(gen_notebook(name, base64.b64encode(data).decode(), digest, worlds, cmd, salt, outrel), indent=1)
    with open(os.path.join(d, "notebook.ipynb"), "w", encoding="utf-8") as f:
        f.write(nb)
    meta = {"id": f"{OWNER}/cora-failure-choice-{name.lower().replace('_', '-')}",
            "title": f"CORA Failure Choice {name.replace('_', ' ')}", "code_file": "notebook.ipynb",
            "language": "python", "kernel_type": "notebook", "is_private": True, "enable_gpu": False,
            "enable_tpu": False, "enable_internet": False, "dataset_sources": [], "competition_sources": [],
            "kernel_sources": [], "model_sources": []}
    with open(os.path.join(d, "kernel-metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    files = {p: sha_bytes(open(os.path.join(REPO, p), "rb").read()) for p in sorted(paths)}
    files.update({k: sha_bytes(open(v, "rb").read()) for k, v in extra.items()})
    with open(os.path.join(d, "PACKAGE.json"), "w", encoding="utf-8") as f:
        json.dump({"archive_sha256": digest, "archive_bytes": len(data), "files_sha256": files, "worlds": worlds,
                   "kernel": meta["id"], "notebook_sha256": sha_bytes(nb.encode())}, f, indent=1, sort_keys=True)
    print(json.dumps({"kernel": meta["id"], "archive_sha256": digest, "bytes": len(data)}))


if __name__ == "__main__":
    if sys.argv[1] == "--generate":
        main_generate(sys.argv[2], sys.argv[3:])
    elif sys.argv[1] == "--generate-test":               # after this revision's GO and the local claim
        main_generate(sys.argv[2], sys.argv[3:], test=True)
    elif sys.argv[1] == "--view-only":                   # development only
        main(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:], mode="--view-only")
    else:
        main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:])
