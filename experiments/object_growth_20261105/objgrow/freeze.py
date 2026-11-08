"""Write FREEZE.json: the sha256 of every file of this study (code, launch scripts, run records, kernel manifests,
notes and report) and of every reused file it executes or reads. Run once at the end of development; a change
after that is a dated amendment with a new freeze.

    python -I run.py freeze
"""
import glob
import os

from objgrow import env as E

REUSED = (["experiments/capability_growth_20261027/cgrow/" + m + ".py"
           for m in ("__init__", "controller", "lang0", "paths", "probes", "schema", "search", "selfext_core")]
          + ["experiments/architecture_sweep_20261026/a2/" + m + ".py"
             for m in ("__init__", "arcdsl", "bus", "corpus", "grammars", "library")]
          + ["experiments/architecture_sweep_20261026/a2/out/corpus.json"]
          + ["experiments/architecture_sweep_20261026/harness/" + m + ".py"
             for m in ("__init__", "data", "ledger", "paths")]
          + ["experiments/architecture_sweep_20261026/splits/SPLITS_MANIFEST.json"]
          + ["outputs/search_components/resources_20261026/github/arc-dsl/" + f
             for f in ("LICENSE", "arc_types.py", "constants.py", "dsl.py", "solvers.py")]
          + ["experiments/natural_growth_20261105/ngrow/" + m + ".py"
             for m in ("__init__", "env", "data", "plugin", "score", "gate")]
          + ["experiments/natural_growth_20261105/split/SPLIT.json"]
          + ["experiments/natural_growth_20261105/feasibility/controller_source_shard" + str(i) + ".jsonl"
             for i in (0, 1)])
DATA = "/path/to/benchmark_data/prepared"


def rel(p):
    return os.path.relpath(os.path.realpath(p), os.path.realpath(E.REPO))


def main():
    st = os.path.realpath(E.STUDY)
    own = sorted(glob.glob(os.path.join(st, "objgrow", "*.py")) + glob.glob(os.path.join(st, "launch", "*.sh"))
                 + [os.path.join(st, "run.py")]
                 + glob.glob(os.path.join(st, "runs", "**", "*.json"), recursive=True)
                 + glob.glob(os.path.join(st, "runs", "kaggle", "*", "kernel-metadata.json"))
                 + glob.glob(os.path.join(st, "*.md")))
    files = {rel(p): E.sha_file(p) for p in own if os.path.basename(p) != "FREEZE.json"}
    files.update({p: E.sha_file(os.path.join(E.REPO, p)) for p in REUSED})
    data = {f"{b}/{f}": E.sha_file(os.path.join(DATA, b, f))
            for b in ("concept_arc", "mini_arc", "1d_arc") for f in ("real.json", "meta.json")}
    out = {"study": "object_growth_20261105", "files_sha256": dict(sorted(files.items())), "data_sha256": data,
           "data_root": DATA,
           "arc_training_sha256": E.sha_file(os.path.join(E.REPO, "outputs", "score_first", "data",
                                                          "arc-agi_training_challenges.json")),
           "never_opened": ["held halves of the three benchmarks", "solutions_scorer_only (held tasks)",
                            "outputs/score_first/data/arc-agi_evaluation_*.json", "the sealed confirmation split"]}
    E.dump(os.path.join(E.STUDY, "FREEZE.json"), out)
    print(len(files), "files frozen; FREEZE.json sha256", E.sha_file(os.path.join(E.STUDY, "FREEZE.json")))


if __name__ == "__main__":
    main()
