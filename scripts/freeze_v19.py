"""Freeze the v1.9 engine-stability package (manifest + .sha256).

Writes outputs/tti/v19_prospective_exclusion.json (E_dev plus every target
digest of the v1.9 development corpus) if absent, then the manifest
outputs/tti/engine_stability_v19_manifest.json pinning the protocol, every
implementation file, every dependency tree (cora_v19 included), the
external files the v1.8 package pins, runtime versions, K*, K*', the
exclusion set and the prospective thresholds.

  python scripts/freeze_v19.py [STATUS]
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_arc2026 import v17_compiler as X                        # noqa: E402
from cora_v19 import v19_repair as R                              # noqa: E402
import v19_prospective as PR                                      # noqa: E402

OUTD = os.path.join(HERE, "outputs", "tti")
IMPLEMENTATION = (
    "cora_v19/__init__.py", "cora_v19/v19_trace.py", "cora_v19/v19_audit.py", "cora_v19/v19_repair.py",
    "scripts/v19_audit_dev.py", "scripts/v19_audit_analyze.py", "scripts/v19_repair_dev.py",
    "scripts/v19_prospective.py", "scripts/v19_feasibility.py", "scripts/freeze_v19.py",
    "scripts/v19_falseaccept_dev.py", "scripts/v19_falseaccept_reduced_dev.py",
    "scripts/v19_clause_safety_dev.py", "scripts/freeze_v19_audit.py",
    "outputs/tti/v19_falseaccept_dev_report.json", "outputs/tti/v19_falseaccept_reduced_dev_report.json",
    "outputs/tti/v19_clause_safety_dev_report.json",
    "logs/v19/verify_prospective.py",
    "tests/test_v19_audit.py", "tests/test_v19_repair.py", "tests/test_v19_prospective.py",
    "cora_arc2026/v18_proposer.py", "cora_arc2026/v17_compiler.py", "cora_arc2026/v14_loc.py",
    "scripts/v18_corpus.py", "scripts/v18_prospective.py",
    "outputs/tti/v18_frozen_d.json", "outputs/tti/no_oracle_proposer_v18_manifest.json",
    "outputs/tti/v19_audit_prefreeze_manifest.json", "outputs/tti/v19_audit_report.json",
    "outputs/tti/v19_repair_dev_report.json", "outputs/tti/v19_feasibility.json",
    "outputs/tti/v19_dev_corpus.json", "outputs/tti/v19_dev_exclusion.json",
    "records/ITEM2_V19_AUDIT_DIAGNOSIS.md", "records/ITEM2_V19_REPAIR_DEVELOPMENT.md",
    "records/ITEM2_V19_FEASIBILITY.md")
PROTOCOL = "docs/CORA_TTI_ENGINE_STABILITY_AUDIT_v1.9.md"


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def exclusion():
    path = os.path.join(OUTD, "v19_prospective_exclusion.json")
    if os.path.exists(path):
        return path
    e_dev = set(json.load(open(os.path.join(OUTD, "v19_dev_exclusion.json")))["target_digests"])
    dev = {t["digest"] for t in json.load(open(os.path.join(OUTD, "v19_dev_corpus.json")))["tasks"]}
    body = sorted(e_dev | dev)
    json.dump({"sources": ["outputs/tti/v19_dev_exclusion.json (3,847)",
                           "outputs/tti/v19_dev_corpus.json target digests (60)"],
               "total": len(body), "target_digests": body}, open(path, "w"), indent=0)
    return path


def main():
    status = sys.argv[1] if len(sys.argv) > 1 else "FROZEN_NOT_PROSPECTIVELY_TESTED"
    excl = exclusion()
    v18 = json.load(open(os.path.join(OUTD, "no_oracle_proposer_v18_manifest.json")))
    deps = {name: L.tree_digest(root) for name, root in L.dependency_roots(HERE).items()}
    deps["cora_v19"] = L.tree_digest(os.path.join(HERE, "cora_v19"))
    man = {"status": status, "protocol_doc": PROTOCOL, "protocol_doc_sha256": sha(os.path.join(HERE, PROTOCOL)),
           "implementation_sha256": {p: sha(os.path.join(HERE, p)) for p in IMPLEMENTATION},
           "dependency_tree_sha256": deps,
           "external_file_sha256": v18["external_file_sha256"],
           "runtime_versions": L.runtime_versions(),
           "k_identity": X.k_identity(), "repair_identity": R.repair_identity(),
           "repair_rule": R.REPAIR_RULE,
           "prospective_exclusion": os.path.relpath(excl, HERE),
           "prospective_exclusion_sha256": sha(excl),
           "seed_ranges": {"development": 870_000_000, "prospective": PR.SEED_BASE},
           "thresholds": {"N_TASKS": PR.N_TASKS, "W_MIN": PR.W_MIN, "DELTA_MIN": PR.DELTA_MIN,
                          "ALPHA": PR.ALPHA, "WORKERS": PR.WORKERS},
           "prefreeze_manifest_sha256": sha(os.path.join(OUTD, "v19_audit_prefreeze_manifest.json"))}
    path = os.path.join(OUTD, "engine_stability_v19_manifest.json")
    with open(path, "w") as fh:
        json.dump(man, fh, indent=1, sort_keys=True)
        fh.write("\n")
    digest = sha(path)
    with open(path + ".sha256", "w") as fh:
        fh.write(f"{digest}  engine_stability_v19_manifest.json\n")
    print(digest)


if __name__ == "__main__":
    main()
