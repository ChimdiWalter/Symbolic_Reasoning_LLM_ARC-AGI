#!/usr/bin/env python3
"""Build the CORA-ONLY-G3 Kaggle package and stage the private dataset and the notebooks (CONFIG.md).

  python kaggle/cora_original_2026/build_package.py [--out outputs/kaggle_deploy/cora_original_2026]

Package (one .tar.gz, which Kaggle unpacks): the UNCHANGED native v23 tree from kaggle/native_v1's frozen archive,
copies of CORA's typed packages (cora_neural_v2, v2g2, v2g3, v2g4; .py files only; EXCLUDE lists the g3
modules the search never imports), the two symbolic modules of
cora_neural_v1 (ir, space) and its __init__, cora_only.py and CONFIG.md, plus PACKAGE_MANIFEST.json (path -> sha256).
A provenance audit refuses to build if any packaged file mentions NVARC, Qwen or a model runtime, or if any file
outside the allow-list is present.

Notebooks (kernel folders with kernel-metadata.json, always private, internet off, no accelerator):
- submit: `cora-only-g3-arc-agi-2`, the competition test file, variant G3: the submission candidate;
- dev_a:  `cora-only-g3-dev-eval-a`, the public evaluation challenges, native + G3, then the scoring cell;
- dev_b:  `cora-only-g3-dev-eval-b`, the public evaluation challenges, search only (C2 then C1), then scoring.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
NATIVE_TAR = os.path.join(REPO, "kaggle", "native_v1", "arc_native_baseline_v1.tar.gz")
NATIVE_TAR_SHA = "4b320ba2fe92b12bcc4345ef4523ca45115f7694e3ab999dfea6b1cfe3c9a088"
PACKAGES = ("cora_neural_v2", "cora_neural_v2g2", "cora_neural_v2g3", "cora_neural_v2g4")
V1_FILES = ("__init__.py", "ir.py", "space.py")
#: g3 modules the search never imports without neural proposals (none are given): the interface spec, the
#: revision controller and the syn-v3 task generator stay out of the package
EXCLUDE = {"cora_neural_v2g3": {"neural.py", "revision.py", "families_v3.py"}}
OWNER = "chimdiwalter"
DATASET = "cora-only-g3-solver-2026"
COMP = "arc-prize-2026-arc-agi-2"
#: text that must not appear in any packaged CORA file (the native tree is the frozen, audited native_v1 archive)
FORBIDDEN_TEXT = re.compile(r"nvarc|qwen|unsloth|vllm|transformers|import torch|from torch|safetensors|peft", re.I)
KERNELS = {
    "submit": ("cora-only-g3-arc-agi-2", "CORA-ONLY-G3 ARC-AGI-2", {"K_MODE": "submit", "K_VARIANTS": "G3"}, False),
    "dev_a": ("cora-only-g3-dev-eval-a", "CORA-ONLY-G3 dev eval A", {"K_MODE": "dev", "K_VARIANTS": "G3"}, True),
    "dev_b": ("cora-only-g3-dev-eval-b", "CORA-ONLY-G3 dev eval B",
              {"K_MODE": "dev", "K_VARIANTS": "C2,C1", "K_SKIP_NATIVE": "1"}, True),
}


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def stage_tree(dest, packages=PACKAGES):
    if sha(NATIVE_TAR) != NATIVE_TAR_SHA:
        raise SystemExit("the frozen native_v1 archive changed")
    with tarfile.open(NATIVE_TAR) as t:
        t.extractall(dest)
    native_files = sorted(os.path.relpath(os.path.join(d, f), dest) for d, _, fs in os.walk(dest) for f in fs)
    added = []
    for pkg in packages:
        os.makedirs(os.path.join(dest, pkg))
        for f in sorted(os.listdir(os.path.join(REPO, pkg))):
            if f.endswith(".py") and f not in EXCLUDE.get(pkg, set()):
                shutil.copy(os.path.join(REPO, pkg, f), os.path.join(dest, pkg, f))
                added.append(f"{pkg}/{f}")
    os.makedirs(os.path.join(dest, "cora_neural_v1"))
    for f in V1_FILES:
        shutil.copy(os.path.join(REPO, "cora_neural_v1", f), os.path.join(dest, "cora_neural_v1", f))
        added.append(f"cora_neural_v1/{f}")
    for f in ("cora_only.py", "CONFIG.md"):
        shutil.copy(os.path.join(HERE, f), os.path.join(dest, f))
        added.append(f)
    return native_files, added


def audit(dest, added):
    """Every added file is in the allow-list and free of forbidden text; returns the problems."""
    probs = []
    for rel in added:
        text = open(os.path.join(dest, rel), encoding="utf-8").read()
        if rel not in ("cora_only.py", "CONFIG.md") and FORBIDDEN_TEXT.search(text):
            probs.append(f"{rel}: {FORBIDDEN_TEXT.search(text).group(0)}")
    # cora_only.py and CONFIG.md name the forbidden things only to forbid them: check they import none of them
    for rel in ("cora_only.py",):
        for line in open(os.path.join(dest, rel), encoding="utf-8"):
            if re.match(r"\s*(import|from)\s+(torch|transformers|unsloth|vllm|peft|safetensors)", line):
                probs.append(f"{rel}: {line.strip()}")
    return probs


def notebook(env, dev):
    """A minimal nbformat-4 notebook: cell 1 sets the mode, cell 2 is cora_only.py (runs main), cell 3 scores (dev)."""
    src = open(os.path.join(HERE, "cora_only.py"), encoding="utf-8").read()
    cells = [{"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
              "source": "import os\n" + "".join(f"os.environ[{k!r}] = {v!r}\n" for k, v in env.items())},
             {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src}]
    if dev:
        cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                      "source": "# separate scoring cell: runs only after every prediction is written\nscore_dev()\n"})
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--g5", action="store_true",
                    help="build the separate G5 development package (own dataset, one dev kernel); the G3 build is unchanged")
    a = ap.parse_args()
    global DATASET, KERNELS
    packages, label = PACKAGES, "CORA-ONLY-G3"
    if a.g5:
        packages, label = PACKAGES + ("cora_neural_v2g5",), "CORA-ONLY-G5 (development)"
        DATASET = "cora-only-g5-solver-2026"
        KERNELS = {"dev_g5": ("cora-only-g5-dev-eval", "CORA-ONLY-G5 dev eval", {"K_MODE": "dev", "K_VARIANTS": "G5"}, True)}
    a.out = a.out or os.path.join(REPO, "outputs", "kaggle_deploy", "cora_original_2026" + ("_g5" if a.g5 else ""))
    shutil.rmtree(a.out, ignore_errors=True)
    tmp = tempfile.mkdtemp()
    name = "cora_only_g5_solver" if a.g5 else "cora_only_g3_solver"
    tree = os.path.join(tmp, name)
    os.makedirs(tree)
    native_files, added = stage_tree(tree, packages)
    probs = audit(tree, added)
    if probs:
        raise SystemExit(f"provenance audit failed: {probs}")
    files = sorted(os.path.relpath(os.path.join(d, f), tree) for d, _, fs in os.walk(tree) for f in fs)
    manifest = {"label": label, "version": "cora_original_2026_v1" + ("_g5" if a.g5 else ""), "native_archive_sha256": NATIVE_TAR_SHA,
                "native_files": len(native_files), "cora_files": added,
                "files": {f: sha(os.path.join(tree, f)) for f in files}}
    json.dump(manifest, open(os.path.join(tree, "PACKAGE_MANIFEST.json"), "w"), indent=1, sort_keys=True)
    ds = os.path.join(a.out, "dataset")
    os.makedirs(ds)
    tar_path = os.path.join(ds, f"{name}.tar.gz")
    with tarfile.open(tar_path, "w:gz") as t:
        t.add(tree, arcname=name, filter=lambda ti: ti if "__pycache__" not in ti.name else None)
    json.dump({"title": "CORA-ONLY-G5 solver 2026" if a.g5 else "CORA-ONLY-G3 solver 2026", "id": f"{OWNER}/{DATASET}", "licenses": [{"name": "other"}],
               "description": "Private research package: the author's own CORA engine (native v23 + typed packages). "
                              "All rights reserved by the author; if a prize were awarded, the competition's CC BY 4.0 "
                              "winner licence would apply."}, open(os.path.join(ds, "dataset-metadata.json"), "w"), indent=1)
    for key, (slug, title, env, dev) in KERNELS.items():
        kd = os.path.join(a.out, f"kernel_{key}")
        os.makedirs(kd)
        json.dump(notebook(env, dev), open(os.path.join(kd, "notebook.ipynb"), "w"), indent=1)
        json.dump({"id": f"{OWNER}/{slug}", "title": title, "code_file": "notebook.ipynb", "language": "python",
                   "kernel_type": "notebook", "is_private": True, "enable_gpu": False, "enable_tpu": False,
                   "enable_internet": False, "dataset_sources": [f"{OWNER}/{DATASET}"],
                   "competition_sources": [COMP], "kernel_sources": [], "model_sources": []},
                  open(os.path.join(kd, "kernel-metadata.json"), "w"), indent=1)
    rec = {"tarball": tar_path, "tarball_sha256": sha(tar_path), "files": len(files) + 1, "cora_files": len(added),
           "native_files": len(native_files), "cora_only_sha256": sha(os.path.join(HERE, "cora_only.py")),
           "kernels": {k: f"{OWNER}/{v[0]}" for k, v in KERNELS.items()}}
    json.dump(rec, open(os.path.join(a.out, "BUILD_RECORD.json"), "w"), indent=1)
    shutil.rmtree(tmp)
    print(json.dumps(rec, indent=1))


if __name__ == "__main__":
    main()
