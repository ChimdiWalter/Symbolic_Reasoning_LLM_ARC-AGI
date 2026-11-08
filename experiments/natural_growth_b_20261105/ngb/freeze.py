"""Write FREEZE.json: the sha256 of the protocol and its amendments, the code (this study's, study A's reused
modules, the growth code, A2 and arc-dsl), the configuration, the split, the benchmark files, the stage 1 and stage
2 records, the frozen libraries, the power and check records, the incident record, the superseded freeze
(FREEZE_V1.json), and a slot for the object-growth code (filled by a dated amendment when the builder's freeze is
announced; `object_growth.code_sha256` null until then). PROGRESS.md is a living log and is not frozen; the tracked
incident record is.

    python -I run.py freeze [OBJECT_GROWTH_FOLDER]      with the folder: fills the slot from the builder's freeze
"""
import glob
import json
import os
import sys

from ngb import env as E

REUSED_A = ["experiments/natural_growth_20261105/" + f for f in
            ("run.py", "split/SPLIT.json", "ngrow/__init__.py", "ngrow/env.py", "ngrow/data.py", "ngrow/plugin.py",
             "ngrow/grow.py", "ngrow/held.py", "ngrow/score.py", "ngrow/analysis.py", "ngrow/bench.py",
             "ngrow/gate.py", "ngrow/controller_run.py")]
REUSED = (["experiments/capability_growth_20261027/cgrow/" + m + ".py"
           for m in ("__init__", "controller", "lang0", "paths", "probes", "schema", "search", "selfext_core")]
          + ["experiments/architecture_sweep_20261026/a2/" + m + ".py"
             for m in ("__init__", "arcdsl", "bus", "corpus", "grammars", "library")]
          + ["experiments/architecture_sweep_20261026/a2/out/corpus.json"]
          + ["experiments/architecture_sweep_20261026/harness/" + m + ".py"
             for m in ("__init__", "data", "ledger", "paths")]
          + ["outputs/search_components/resources_20261026/github/arc-dsl/" + f
             for f in ("LICENSE", "arc_types.py", "constants.py", "dsl.py", "solvers.py")])
#: this study's modules a kernel never runs (and study A's two that only its phase 1 used); the kernel's inference
#: closure (env, gate, ops, held, arc2, phase2, bench_probe, object_arm, score, the builder's objgrow) is packaged and
#: exercised by ngb/package_smoke.py inside the extracted archive
ATHE_ONLY_CODE = ("discover", "library", "freeze", "kaggle_build", "report", "power", "power_object", "dry_run",
                  "seed_check", "admission_tests", "object_registries", "object_costs")
#: study A's records this study's phase 1 read (power and cost inputs); frozen, Athe-only (amendment 3)
STUDY_A_RECORDS = ("experiments/natural_growth_20261105/feasibility/FEASIBILITY.json",
                   "experiments/natural_growth_20261105/feasibility/controller_source_shard0.jsonl",
                   "experiments/natural_growth_20261105/feasibility/controller_source_shard1.jsonl")
ATHE_ONLY_A = ("experiments/natural_growth_20261105/ngrow/controller_run.py",
               "experiments/natural_growth_20261105/ngrow/grow.py")


def rel(p):
    return os.path.relpath(os.path.realpath(p), os.path.realpath(E.REPO))


def object_growth_slot(folder):
    """The builder's frozen files the arms need, pinned by the digests of the builder's own FREEZE.json (which must
    have the digest recorded in the configuration); code_sha256 is that FREEZE.json's digest."""
    if not folder:
        return {"folder": "experiments/object_growth_20261105", "code_sha256": None, "files_sha256": {},
                "status": "slot: filled by a dated amendment when the builder announces its code freeze"}
    cfg = E.load(os.path.join(E.STUDY, "config", "STUDY_CONFIG.json"))["object_growth"]
    bf = os.path.join(E.REPO, folder, cfg.get("builder_freeze_file", "FREEZE.json"))
    digest = E.sha_file(bf)
    if digest != cfg["builder_freeze_sha256"]:
        raise SystemExit(f"the builder's freeze digest {digest} is not the announced one")
    builder = E.load(bf)["files_sha256"]
    need = sorted(glob.glob(os.path.join(E.REPO, folder, "objgrow", "*.py"))) + \
        [os.path.join(E.REPO, r) for r in cfg["registries"].values()] + \
        [os.path.join(E.REPO, folder, f) for f in ("runs/v2/FUNNEL.json", "REPORT_DEV.md")] + \
        [os.path.join(E.REPO, folder, "runs", "v2", b, "reuse.json") for b in ("concept_arc", "mini_arc", "1d_arc")] + \
        sorted(glob.glob(os.path.join(E.REPO, folder, "CONTRACT_AMENDMENT_*.md")))
    fs = {}
    for p in need:
        r = rel(p)
        if r not in builder:
            raise SystemExit(f"{r} is not in the builder's freeze")
        if E.sha_file(p) != builder[r]:
            raise SystemExit(f"{r} differs from the builder's frozen digest")
        fs[r] = builder[r]
    fs[rel(bf)] = digest
    for prior in cfg.get("builder_prior_freezes", []):          # an earlier freeze the current one supersedes
        fs[prior["path"]] = prior["sha256"]
        if E.sha_file(os.path.join(E.REPO, prior["path"])) != prior["sha256"]:
            raise SystemExit(f"{prior['path']} differs from its recorded digest")
    return {"folder": folder, "files_sha256": fs, "code_sha256": digest, "builder_commit": cfg["builder_commit"],
            "builder_freeze_file": rel(bf), "status": "frozen (amendment 2)"}


def main(object_growth_folder=None):
    st = os.path.realpath(E.STUDY)
    own_code = sorted(glob.glob(os.path.join(st, "ngb", "*.py"))) + [os.path.join(st, "run.py")]
    kernel_records = sorted(glob.glob(os.path.join(st, "feasibility", "library", "*.json")) +
                            glob.glob(os.path.join(st, "feasibility", "library", "*", "*.json")) +
                            glob.glob(os.path.join(st, "feasibility", "object_registries.json")) +
                            glob.glob(os.path.join(st, "feasibility", "object_costs.json")))
    athe_records = sorted(glob.glob(os.path.join(st, "feasibility", "*.jsonl")) +
                          glob.glob(os.path.join(st, "power", "*.json")) +
                          [p for p in glob.glob(os.path.join(st, "checks", "*.json"))
                           if not p.endswith("PACKAGE_CHECK.json")] +
                          glob.glob(os.path.join(st, "checks", "*", "RESULTS.json")) +
                          glob.glob(os.path.join(st, "records", "*.md")) +
                          glob.glob(os.path.join(st, "checks", "kaggle_rehearsal", "*.json")) +
                          glob.glob(os.path.join(st, "checks", "kaggle_rehearsal", "*.md")) +
                          glob.glob(os.path.join(st, "rehearsal", "*.json")) +
                          [p for p in (os.path.join(st, "FREEZE_V1.json"), os.path.join(st, "FREEZE_V2.json"),
                                       os.path.join(st, "FREEZE_V3.json"), os.path.join(st, "NOTES_FROM_PHASE1_SESSION.md"))
                           if os.path.exists(p)])
    docs = [os.path.join(st, p) for p in ("PROTOCOL.md", "config/STUDY_CONFIG.json")] + \
        sorted(glob.glob(os.path.join(st, "PROTOCOL_AMENDMENT_*.md")))
    files = {rel(p): E.sha_file(p) for p in own_code + kernel_records + athe_records + docs}
    files.update({p: E.sha_file(os.path.join(E.REPO, p)) for p in REUSED + REUSED_A + list(STUDY_A_RECORDS)})
    athe_only = sorted([rel(p) for p in athe_records] +
                       [rel(p) for p in own_code if os.path.basename(p)[:-3] in ATHE_ONLY_CODE] + list(ATHE_ONLY_A) +
                       list(STUDY_A_RECORDS))
    data = {f"{b}/{f}": E.sha_file(os.path.join(E.DATA, b, f))
            for b in ("concept_arc", "mini_arc", "1d_arc") for f in ("real.json", "meta.json")}
    out = {"study": "natural_growth_b_20261105", "version": 4,
           "protocol_sha256": files[rel(os.path.join(st, "PROTOCOL.md"))],
           "amendments_sha256": {rel(p): files[rel(p)] for p in docs if "AMENDMENT" in p},
           "config_sha256": files[rel(os.path.join(st, "config/STUDY_CONFIG.json"))],
           "split_sha256": files["experiments/natural_growth_20261105/split/SPLIT.json"],
           "files_sha256": dict(sorted(files.items())), "athe_only": athe_only, "data_sha256": data,
           "data_root": "/path/to/benchmark_data/prepared (Athe); data/prepared "
                        "in a package",
           "scorer_only_sha256": {f"{b}/solutions_scorer_only/solutions.json":
                                  E.sha_file(os.path.join(E.DATA, b, "solutions_scorer_only", "solutions.json"))
                                  for b in ("concept_arc", "mini_arc", "1d_arc")},
           "arc_agi_2_sha256": {"outputs/score_first/data/arc-agi_evaluation_challenges.json":
                                "e7c62a4bd211867c6b538f66b8013b81f299663c82ca062f49a52bf439d6e4e8",
                                "outputs/score_first/data/arc-agi_evaluation_solutions.json":
                                "84be4f4f39b79e82c36d565fc878830988b094917f052ee7069aef30b33ca8f1"},
           "object_growth": object_growth_slot(object_growth_folder),
           "not_frozen": ["PROGRESS.md (living log)", "logs/", "runs/", "gates.pkl caches",
                          "checks/PACKAGE_CHECK.json (a check of this freeze, run after it; committed, reported)"]}
    E.dump(os.path.join(st, "FREEZE.json"), out)
    print(json.dumps({"protocol_sha256": out["protocol_sha256"], "amendments": out["amendments_sha256"],
                      "files": len(files), "object_growth": out["object_growth"]["status"],
                      "freeze_sha256": E.sha_file(os.path.join(st, "FREEZE.json"))}))


if __name__ == "__main__":
    main(*sys.argv[1:])
