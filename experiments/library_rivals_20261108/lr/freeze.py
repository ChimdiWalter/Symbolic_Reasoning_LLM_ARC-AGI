"""Writes FREEZE.json: the sha256 of every file the run executes or reads (PROTOCOL.md section 8).

    python3 -I run.py freeze

Own files (protocol, configuration, code, the built libraries, the launcher, the dry run's record); reused code
(study A's ngrow, the growth code cgrow, A2's a2 with its solver corpus, the arc-dsl source, the object-level
builder's objgrow); the frozen inputs (study A's split, study B's discovery records, the builder's registries); the
benchmark input files (demonstrations and test inputs). The solution files are not hashed here: their digests are
the ones study B's freeze recorded (config), and the scorer checks them after the seal.
"""
import glob
import os

from lr import env as E


def rel(p):
    return os.path.relpath(os.path.realpath(p), E.REPO)


def main():
    st = E.STUDY
    own = [os.path.join(st, p) for p in ("PROTOCOL.md", "run.py", os.path.join("config", "CONFIG.json"),
                                         os.path.join("libraries", "LIBRARIES.json"))]
    own += sorted(glob.glob(os.path.join(st, "lr", "*.py"))) + sorted(glob.glob(os.path.join(st, "launch", "*.sh")))
    own += sorted(glob.glob(os.path.join(st, "checks", "*", "RESULTS.json"))) + \
        sorted(glob.glob(os.path.join(st, "checks", "*.json")))
    reused = []
    for d in (os.path.join(E.STUDY_A, "ngrow"), os.path.join(E.REPO, "experiments", "capability_growth_20261027", "cgrow"),
              os.path.join(E.REPO, "experiments", "architecture_sweep_20261026", "a2"), os.path.join(E.OBJ, "objgrow")):
        reused += sorted(glob.glob(os.path.join(d, "*.py")))
    reused += sorted(glob.glob(os.path.join(E.REPO, "experiments", "architecture_sweep_20261026", "harness", "*.py")))
    reused += [os.path.join(E.REPO, "experiments", "architecture_sweep_20261026", "a2", "out", "corpus.json"),
               os.path.join(E.STUDY_A, "split", "SPLIT.json")]
    reused += sorted(glob.glob(os.path.join(E.REPO, "outputs", "search_components", "resources_20261026", "github",
                                            "arc-dsl", "*.py")))
    reused += [os.path.join(E.STUDY_B, "feasibility", f"discover_shard{i}.jsonl") for i in (0, 1)]
    reused += [os.path.join(E.OBJ, "runs", "v2", b, "registry.json") for b in ("concept_arc", "mini_arc", "1d_arc")]
    files = {rel(p): E.sha_file(p) for p in own + reused}
    data = {f"{b}/{f}": E.sha_file(os.path.join(E.DATA, b, f))
            for b in ("concept_arc", "mini_arc", "1d_arc") for f in ("real.json", "meta.json")}
    cfg = E.load(os.path.join(st, "config", "CONFIG.json"))
    out = {"study": "library_rivals_20261108", "protocol_sha256": files[rel(os.path.join(st, "PROTOCOL.md"))],
           "files_sha256": dict(sorted(files.items())), "data_sha256": data, "data_root": E.DATA,
           "scorer_only_sha256": cfg["scorer_only_sha256_from_study_b_freeze_9d9d2248"],
           "launch_sha256": {rel(p): E.sha_file(p) for p in (os.path.join(E.REPO, "scripts", "run_detached.sh"),
                                                             os.path.join(E.REPO, "scripts", "with_cpu_slot.sh"))},
           "not_frozen": ["PROGRESS.md", "logs/", "runs/", "GO (written after the freeze)"]}
    E.dump(os.path.join(st, "FREEZE.json"), out)
    print(len(files), "files;", "FREEZE.json", E.sha_file(os.path.join(st, "FREEZE.json")))
