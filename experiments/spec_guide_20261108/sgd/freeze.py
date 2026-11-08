"""Write FREEZE.json: the sha256 of every file the held run executes or reads (the Kaggle package), of the
development code, records and data it rests on, and the Athe environment. `athe_only` lists the frozen files the
package does not carry (the gate skips them inside the package).

    python3 -s -B sgd/freeze.py
"""
import glob
import hashlib
import json
import os
import platform
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kaggle_held as KH                                                            # noqa: E402

STUDY, REPO, REL = KH.STUDY, KH.REPO, KH.REL


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def rel(p):
    return os.path.relpath(p, REPO)


def main():
    package = [p for p in KH.CODE if p != REL + "/FREEZE.json"]
    athe = sorted(set(
        [rel(p) for p in glob.glob(os.path.join(STUDY, "sgd", "*.py"))] +
        [REL + "/DESIGN_NOTE.md", REL + "/run.py"] +
        [rel(p) for p in glob.glob(os.path.join(STUDY, "launch", "*"))] +
        [rel(p) for p in glob.glob(os.path.join(STUDY, "dev", "v*", "*.json"))] +
        [rel(p) for p in glob.glob(os.path.join(STUDY, "dev", "block_models.*.json"))] +
        [rel(p) for p in glob.glob(os.path.join(STUDY, "dev", "kaggle", "*", "*"))] +
        [rel(p) for p in glob.glob(os.path.join(STUDY, "runs", "kaggle_dev", "*", "*"))]) - set(package))
    athe = [p for p in athe if os.path.isfile(os.path.join(REPO, p))]
    files = sorted(set(package) | set(athe))
    import numpy
    import torch
    doc = {"study": "specification-reading guide test (experiments/spec_guide_20261108)", "version": 1,
           "protocol_sha256": sha(os.path.join(STUDY, "PROTOCOL.md")),
           "design_note_sha256": sha(os.path.join(STUDY, "DESIGN_NOTE.md")),
           "files_sha256": {p: sha(os.path.join(REPO, p)) for p in files},
           "athe_only": athe,
           "config": json.load(open(os.path.join(STUDY, "config", "CONFIG.json"))),
           "environment_athe": {"python": platform.python_version(), "numpy": numpy.__version__,
                                "torch": torch.__version__},
           "public_training_challenges_sha256": "779eaba89790ebad9af02514a7efc0aefaf2cf8236f046a31bbf8b9ec48f20f5",
           "never_opened": ["any held family or held-pool grid", "the public training solutions file",
                            "the held halves' test outputs", "any ARC-AGI-2 evaluation file"]}
    with open(os.path.join(STUDY, "FREEZE.json"), "w") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
    print(json.dumps({"freeze_sha256": sha(os.path.join(STUDY, "FREEZE.json")), "files": len(files),
                      "athe_only": len(athe)}))


if __name__ == "__main__":
    main()
