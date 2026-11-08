"""Build the private Kaggle CPU kernel of the held run (standard library only).

    python3 -s -B sgd/kaggle_held.py candidate     the package without the GO (reviewed bytes; smoke test)
    python3 -s -B sgd/kaggle_held.py final         after the GO: the same files plus runs/GO (refused unless the GO
                                                   names this protocol and this freeze and every other file equals
                                                   the candidate manifest)
One kernel (SGHELD, chimdiwalter/cora-spec-guide-held): private, CPU only, internet off; 4 workers; generation
capped at GEN_LIMIT_S, the arms at RUN_LIMIT_S. The package holds code, frozen models, the configuration and the
public training challenges (input grids only are used); never a solution file.
"""
import base64
import hashlib
import json
import os
import sys

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(STUDY))
REL = os.path.relpath(STUDY, REPO)
sys.path.insert(0, os.path.join(STUDY, "sgd"))
import kaggle_dev as KD                                                             # noqa: E402

GC = "experiments/guided_construction_20261106/"
CODE = ([p for p in KD.CODE if not p.startswith(REL + "/launch/devgen") and not p.startswith(REL + "/sgd/")]
        + [GC + "gcon/" + m + ".py" for m in ("model", "policy")]
        + [REL + "/sgd/" + m + ".py" for m in ("__init__", "env", "gen", "net", "train", "data", "held", "gate",
                                                "score")]
        + [REL + "/" + p for p in ("PROTOCOL.md", "FREEZE.json", "config/CONFIG.json", "models/spec_guide.pt",
                                   "models/block_models.json", "launch/held_kernel.py")])
CODE = sorted(set(CODE))
OWNER = "chimdiwalter"
WORKERS, PER_EDIT, GEN_LIMIT_S, RUN_LIMIT_S = 4, 60, 9000, 9000


def build(mode):
    ents = [(p, os.path.join(REPO, p)) for p in CODE]
    if mode == "final":
        ents.append((REL + "/runs/GO", os.path.join(STUDY, "runs", "GO")))
    for rel, _ in ents:
        if "solutions" in rel or "evaluation" in rel:
            raise SystemExit(f"refused: {rel}")
    files = {rel: hashlib.sha256(open(src, "rb").read()).hexdigest() for rel, src in sorted(ents)}
    kdir = os.path.join(STUDY, "runs", "kaggle")
    os.makedirs(kdir, exist_ok=True)
    if mode == "final":
        # the git custody checks (the GO committed alone and unchanged; its freeze commit the last that changed
        # FREEZE.json) run on Athe here, through the study's gate
        import subprocess
        p = subprocess.run([sys.executable, "-s", "-B", os.path.join(STUDY, "run.py"), "gate", "check"],
                           capture_output=True, text=True, env=dict(os.environ, PYTHONHASHSEED="0"))
        if p.returncode != 0:
            raise SystemExit("gate check refused: " + (p.stdout + p.stderr)[-500:])
        cand = json.load(open(os.path.join(kdir, "PACKAGE_MANIFEST_candidate.json")))
        diff = sorted(k for k in set(cand["files_sha256"]) | set(files) if k != REL + "/runs/GO" and
                      cand["files_sha256"].get(k) != files.get(k))
        if diff:
            raise SystemExit("files differ from the candidate manifest: " + ", ".join(diff))
        go = dict(l.split(": ", 1) for l in open(os.path.join(STUDY, "runs", "GO")).read().splitlines()[1:]
                  if ": " in l)
        if go.get("freeze_json_sha256") != files[REL + "/FREEZE.json"]:
            raise SystemExit("runs/GO does not name this freeze")
    data = KD.GKB.archive(ents)
    digest = hashlib.sha256(data).hexdigest()
    b64 = base64.b64encode(data).decode()
    with open(os.path.join(kdir, f"package_{mode}.tar.gz"), "wb") as f:
        f.write(data)
    head = ("# CORA specification-reading guide: held run\n\nPrivate research run; CPU only, internet off. The package "
            "holds code, frozen models and public training inputs; scoring happens elsewhere, once.")
    unpack = ("import base64, hashlib, io, os, subprocess, sys, tarfile, time\n"
              f"ARCHIVE_SHA256 = '{digest}'\n"
              f"ARCHIVE = base64.b64decode('{b64}')\n"
              "assert hashlib.sha256(ARCHIVE).hexdigest() == ARCHIVE_SHA256, 'package digest mismatch'\n"
              "ROOT = '/kaggle/working/pkg'\n"
              "with tarfile.open(fileobj=io.BytesIO(ARCHIVE), mode='r:gz') as tf:\n"
              "    tf.extractall(ROOT)\n"
              "print('package', ARCHIVE_SHA256, 'cpus', os.cpu_count(), sys.version)\n")
    run = (f"STUDY = os.path.join(ROOT, '{REL}')\n"
           f"p = subprocess.run([sys.executable, '-s', '-B', os.path.join(STUDY, 'launch', 'held_kernel.py'), ROOT, "
           f"'{WORKERS}', '{PER_EDIT}', '{GEN_LIMIT_S}', '{RUN_LIMIT_S}'])\n"
           "print('return code', p.returncode)\n")
    pack = ("out = '/kaggle/working/SGHELD_outputs.tar.gz'\n"
            "with tarfile.open(out, 'w:gz') as tf:\n"
            "    tf.add(os.path.join(STUDY, 'runs', 'held'), arcname='held')\n"
            "print(out, hashlib.sha256(open(out, 'rb').read()).hexdigest())\n")
    cells = [KD.GKB.cell("markdown", head, 1), KD.GKB.cell("code", unpack, 2), KD.GKB.cell("code", run, 3),
             KD.GKB.cell("code", pack, 4)]
    nb = json.dumps({"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                                                 "name": "python3"},
                                                  "language_info": {"name": "python"}},
                     "nbformat": 4, "nbformat_minor": 5}, indent=1)
    d = os.path.join(kdir, "SGHELD" + ("" if mode == "final" else "_candidate"))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "notebook.ipynb"), "w") as f:
        f.write(nb)
    meta = {"id": f"{OWNER}/cora-spec-guide-held", "title": "CORA Spec Guide Held", "code_file": "notebook.ipynb",
            "language": "python", "kernel_type": "notebook", "is_private": True, "enable_gpu": False,
            "enable_tpu": False, "enable_internet": False, "dataset_sources": [], "competition_sources": [],
            "kernel_sources": [], "model_sources": []}
    with open(os.path.join(d, "kernel-metadata.json"), "w") as f:
        json.dump(meta, f, indent=1)
    man = {"mode": mode, "archive_sha256": digest, "archive_bytes": len(data), "files_sha256": files,
           "kernel": {"id": meta["id"], "notebook_sha256": hashlib.sha256(nb.encode()).hexdigest(),
                      "metadata_sha256": hashlib.sha256(open(os.path.join(d, "kernel-metadata.json"),
                                                             "rb").read()).hexdigest()},
           "workers": WORKERS, "per_edit": PER_EDIT, "gen_limit_s": GEN_LIMIT_S, "run_limit_s": RUN_LIMIT_S}
    with open(os.path.join(kdir, f"PACKAGE_MANIFEST_{mode}.json"), "w") as f:
        json.dump(man, f, indent=1, sort_keys=True)
    print(json.dumps({"mode": mode, "archive_sha256": digest, "bytes": len(data),
                      "notebook_sha256": man["kernel"]["notebook_sha256"]}))


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "candidate")
