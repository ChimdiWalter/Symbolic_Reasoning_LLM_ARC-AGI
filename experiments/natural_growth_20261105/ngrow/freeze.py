"""Write FREEZE.json: the sha256 of the protocol, the code (this study's and every reused file), the configuration,
the split, the benchmark files and the phase 1 records. Run once at the end of phase 1; a change after that is a
dated amendment with a new freeze.

    python -I run.py freeze
"""
import glob
import json
import os

from ngrow import env as E

REUSED = (["experiments/capability_growth_20261027/cgrow/" + m + ".py"
           for m in ("__init__", "controller", "lang0", "paths", "probes", "schema", "search", "selfext_core",
                     "episode")]
          + ["experiments/architecture_sweep_20261026/a2/" + m + ".py"
             for m in ("__init__", "arcdsl", "bus", "corpus", "grammars", "library")]
          + ["experiments/architecture_sweep_20261026/a2/out/corpus.json"]
          + ["experiments/architecture_sweep_20261026/harness/" + m + ".py"
             for m in ("__init__", "data", "ledger", "paths")]
          + ["outputs/search_components/resources_20261026/github/arc-dsl/" + f
             for f in ("LICENSE", "arc_types.py", "constants.py", "dsl.py", "solvers.py")])
ATHE_ONLY_CODE = ("checks", "dry_run", "feasibility", "freeze", "kaggle_build", "report", "power")


def rel(p):
    return os.path.relpath(os.path.realpath(p), os.path.realpath(E.REPO))


def main():
    st = os.path.realpath(E.STUDY)
    own_code = sorted(glob.glob(os.path.join(st, "ngrow", "*.py"))) + [os.path.join(st, "run.py")]
    records = sorted(glob.glob(os.path.join(st, "feasibility", "*.json*")) +
                     glob.glob(os.path.join(st, "feasibility", "grow", "*", "*.json")) +
                     glob.glob(os.path.join(st, "power", "*.json")) +
                     glob.glob(os.path.join(st, "checks", "*.json")) +
                     glob.glob(os.path.join(st, "bench", "*.json")))
    files = {rel(p): E.sha_file(p) for p in own_code}
    files.update({p: E.sha_file(os.path.join(E.REPO, p)) for p in REUSED})
    for p in ("PROTOCOL.md", "config/STUDY_CONFIG.json", "split/SPLIT.json"):
        files[rel(os.path.join(st, p))] = E.sha_file(os.path.join(st, p))
    files.update({rel(p): E.sha_file(p) for p in records})
    athe_only = sorted([rel(p) for p in records] +
                       [rel(p) for p in own_code if os.path.basename(p)[:-3] in ATHE_ONLY_CODE] +
                       ["experiments/capability_growth_20261027/cgrow/episode.py"])
    data = {f"{b}/{f}": E.sha_file(os.path.join(E.DATA, b, f))
            for b in ("concept_arc", "mini_arc", "1d_arc") for f in ("real.json", "meta.json")}
    out = {"study": "natural_growth_20261105",
           "protocol_sha256": files[rel(os.path.join(st, "PROTOCOL.md"))],
           "split_sha256": files[rel(os.path.join(st, "split/SPLIT.json"))],
           "config_sha256": files[rel(os.path.join(st, "config/STUDY_CONFIG.json"))],
           "files_sha256": dict(sorted(files.items())), "athe_only": athe_only, "data_sha256": data,
           "data_root": "/path/to/benchmark_data/prepared (Athe); data/prepared "
                        "in a package",
           "scorer_only_sha256": {f"{b}/solutions_scorer_only/solutions.json":
                                  E.sha_file(os.path.join(E.DATA, b, "solutions_scorer_only", "solutions.json"))
                                  for b in ("concept_arc", "mini_arc", "1d_arc")},
           "arc_agi_2_sha256": {"outputs/score_first/data/arc-agi_evaluation_challenges.json":
                                "e7c62a4bd211867c6b538f66b8013b81f299663c82ca062f49a52bf439d6e4e8",
                                "outputs/score_first/data/arc-agi_evaluation_solutions.json":
                                "84be4f4f39b79e82c36d565fc878830988b094917f052ee7069aef30b33ca8f1"}}
    E.dump(os.path.join(st, "FREEZE.json"), out)
    print(json.dumps({"protocol_sha256": out["protocol_sha256"], "files": len(files),
                      "freeze_sha256": E.sha_file(os.path.join(st, "FREEZE.json"))}))


if __name__ == "__main__":
    main()
