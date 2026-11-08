"""Write FREEZE.json (phase 1, last step): sha256 of the protocol, the code, the configuration, the seeds and the
phase 1 records, and of every file outside this folder that phase 2 reads (S1's code, A2, CAST, arc-dsl).

    python3 -I cas/freeze.py

The gate (cas/gate.py) re-checks every entry of "files_sha256" and "dependencies_sha256" before each phase 2 stage.
"""
import glob
import hashlib
import json
import os
import time

STUDY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(STUDY))
FROZEN_GLOBS = ("PROTOCOL.md", "PROTOCOL_REVISION_1.md", "FREEZE_REVISION_1.json", "PROTOCOL_REVISION_2.md",
                "FREEZE_REVISION_2.json", "PROTOCOL_REVISION_3.md", "FREEZE_REVISION_3.json", "cas/*.py",
                "config/STUDY_CONFIG.json", "config/POOLS.json",
                "feasibility/*.json", "pilot/*.json", "pilot_v1_superseded/*.json", "pilot_v2_superseded/*.json",
                "pilot_v3_superseded/*.json", "reviews/*.md", "checks/C7M_BUDGET_SMOKE.json",
                "checks/C7M_RERUN_SMOKE.json",
                "power/*.json", "power/superseded/*.json", "bench/*.json", "checks/EQUIVALENCE.json",
                "checks/ANALYSIS.json", "checks/DRY_RUN_CONFIG.json", "checks/generator_dry_run_pilot/*.json",
                "checks/generator_dry_run_pilot/*/*/*.json", "launch/*.sh")
S1 = "experiments/capability_growth_20261027/"
DEPENDENCIES = ([S1 + "cgrow/" + m + ".py" for m in ("__init__", "controller", "episode", "evaluate", "experiment",
                                                      "invent", "lang0", "naming", "paths", "probes", "prompts",
                                                      "registry", "s1", "schema", "search", "tasks", "testib",
                                                      "testib_rest")]
                + [S1 + f for f in ("protocols/TEST_S1_PROTOCOL.md", "partitions/TEST_S1_FREEZE.json",
                                    "evaluator_only/TASKS_EVAL.json", "runs/s1_eval/results.json")]
                + ["experiments/architecture_sweep_20261026/a2/" + m for m in
                   ("__init__.py", "arcdsl.py", "bus.py", "corpus.py", "grammars.py", "library.py", "out/corpus.json",
                    "out/traces.jsonl")]
                + ["experiments/architecture_sweep_20261026/harness/" + m + ".py" for m in
                   ("__init__", "data", "ledger", "paths")]
                + ["experiments/architecture_sweep_20261026/splits/SPLITS_MANIFEST.json"]
                + ["experiments/cora_cast_20261026/cast/" + m + ".py" for m in ("__init__", "absdom", "contract_check")]
                + ["outputs/search_components/resources_20261026/github/arc-dsl/" + f
                   for f in ("LICENSE", "arc_types.py", "constants.py", "dsl.py", "solvers.py")]
                + ["scripts/with_cpu_slot.sh"])
#: ARC training data the generator reads (inputs, and the outputs of real previously solved tasks); never evaluation
DATA = ("<ARC data folder>/arc-agi_training_challenges.json", "<ARC data folder>/arc-agi_training_solutions.json")
SEEDS = {"generator_salts": {"W1": "cas-W1-20261105", "W2": "cas-W2b-20261105", "W3": "cas-W3-20261105"},
         "pool_salt": "cas-pools-20261105", "pilot_pool_size": 100,
         "structure_order_seeds": [0, 1, 2], "structure_order_rule": "random.Random('s1-order-' + str(seed)).shuffle",
         "PYTHONHASHSEED": 0, "bootstrap_seeds": {"unit": 1, "family": 7, "draws": 10000},
         "power_simulation_seeds": "1000 * F + 10 * m + ord(scenario), numpy default_rng"}


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    files = sorted({os.path.relpath(p, STUDY) for g in FROZEN_GLOBS for p in glob.glob(os.path.join(STUDY, g))})
    doc = {"frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "study": "construction_at_scale_20261105", "revision": 4,
           "supersedes": {"PROTOCOL_REVISION_3.md": sha(os.path.join(STUDY, "PROTOCOL_REVISION_3.md")),
                          "FREEZE_REVISION_3.json": sha(os.path.join(STUDY, "FREEZE_REVISION_3.json")),
                          "PROTOCOL_REVISION_2.md": sha(os.path.join(STUDY, "PROTOCOL_REVISION_2.md")),
                          "FREEZE_REVISION_2.json": sha(os.path.join(STUDY, "FREEZE_REVISION_2.json")),
                          "PROTOCOL_REVISION_1.md": sha(os.path.join(STUDY, "PROTOCOL_REVISION_1.md")),
                          "FREEZE_REVISION_1.json": sha(os.path.join(STUDY, "FREEZE_REVISION_1.json")),
                          "note": "revisions 1 to 3 are kept byte for byte under these names; revision 4 answers "
                                  "the companion study's re-review of revision 3 (note 0487) and the project's own "
                                  "review of revision 3 (reviews/INDEPENDENT_PRE_RUN_REVIEW_REVISION_3.md, commit "
                                  "c7bd34e0): unique and exact rows, typed bounded commitments with the exact grown "
                                  "key set, endpoint re-scoring, controller-summary reconciliation, the matched-search "
                                  "memory rerun, rule 6 in full, main-pool packaging check; scope and cap wording"},
           "protocol_sha256": sha(os.path.join(STUDY, "PROTOCOL.md")),
           "files_sha256": {f: sha(os.path.join(STUDY, f)) for f in files},
           "dependencies_sha256": {d: sha(os.path.join(REPO, d)) for d in DEPENDENCIES},
           "data_sha256": {d: sha(d) for d in DATA},
           "seeds": SEEDS,
           "note": "phase 1 freeze: no main task generated, no method run on any task of this study"}
    with open(os.path.join(STUDY, "FREEZE.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
        f.write("\n")
    print(json.dumps({"FREEZE.json": sha(os.path.join(STUDY, "FREEZE.json")), "protocol": doc["protocol_sha256"],
                      "files": len(files), "dependencies": len(DEPENDENCIES)}))


if __name__ == "__main__":
    main()
