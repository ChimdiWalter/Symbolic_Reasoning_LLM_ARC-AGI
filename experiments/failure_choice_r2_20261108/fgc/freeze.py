"""Write FREEZE.json: the sha256 of every file the held run reads or executes (standard library; run with -I).

    python3 -I fgc/freeze.py

Study files: PROTOCOL.md, fgc/*.py, config/*.json, launch/*.sh, the world copies (runs/worlds/), the source set and
its measurements (runs/source/), the contract checks (checks/). Dependencies (repository paths): the construction
test's cas/env.py, cas/generate.py and cas/__init__.py, and every file of the kernel package (fgc/kaggle_build.py
FILES: S1's cgrow, A2, the harness, CAST, arc-dsl). Data: the ARC training challenges file the generator reads.
"""
import hashlib
import json
import os
import sys

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(STUDY))
sys.path.insert(0, os.path.join(STUDY, "fgc"))
import kaggle_build as KB                                                     # noqa: E402

DATA = ["<ARC data folder>/arc-agi_training_challenges.json"]


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def study_files():
    out = ["PROTOCOL.md"]
    for d, exts in (("fgc", (".py",)), ("config", (".json",)), ("launch", (".sh",)), ("checks", (".json",))):
        for n in sorted(os.listdir(os.path.join(STUDY, d))):
            if n.endswith(exts):
                out.append(f"{d}/{n}")
    for root in ("runs/worlds", "runs/source"):          # (runs/source holds the source set and its measurements)
        for dp, _, fs in os.walk(os.path.join(STUDY, root)):
            for n in sorted(fs):
                out.append(os.path.relpath(os.path.join(dp, n), STUDY))
    return sorted(out)


def main():
    files = {rel: sha(os.path.join(STUDY, rel)) for rel in study_files()}
    study_rel = os.path.relpath(STUDY, REPO)
    deps = {}
    for rel in list(KB.FILES) + list(KB.GEN_FILES):
        if rel.startswith(study_rel + "/"):
            continue
        deps[rel] = sha(os.path.join(REPO, rel))
    r1_test = os.path.relpath(os.path.join(os.path.dirname(STUDY), "failure_choice_20261108", "runs", "test",
                                           "evaluator_only", "TEST_EVAL.json"), REPO)
    deps[r1_test] = sha(os.path.join(REPO, r1_test))
    doc = {"study": "failure_choice_r2_20261108", "files_sha256": files, "dependencies_sha256": dict(sorted(deps.items())),
           "data_sha256": {p: sha(p) for p in DATA}}
    with open(os.path.join(STUDY, "FREEZE.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
        f.write("\n")
    print(json.dumps({"files": len(files), "dependencies": len(deps), "data": len(DATA), "sha256": sha(os.path.join(
        STUDY, "FREEZE.json"))}))


if __name__ == "__main__":
    main()
