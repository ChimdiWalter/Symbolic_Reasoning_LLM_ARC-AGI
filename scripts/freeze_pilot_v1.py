"""Freeze the real ARC pilot v1 (manifest + .sha256).

  python scripts/freeze_pilot_v1.py [STATUS]

Pins the protocol, every pilot implementation file, the selection and the
bundle, the frozen components (v1.7 compiler, v1.8 proposer and its D, the
v1.9 repair, the harness, library.json), every dependency tree, the data and
sealed-record checksums, runtime versions, K* and K*'. The evaluator-only key
map is pinned as well but checked only on the evaluator side
(freeze_problems("evaluator")), so the reasoner side never opens it.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_arc2026 import v17_compiler as X                        # noqa: E402
from cora_v19 import v19_repair as R                              # noqa: E402
from cora_pilot import bundle as B                                # noqa: E402
from cora_pilot import evaluator as EV                            # noqa: E402
from cora_pilot import native as N                                # noqa: E402
from cora_pilot import reasoner as RS                             # noqa: E402

MANIFEST = os.path.join(HERE, "outputs", "pilot_v1", "pilot_v1_manifest.json")
PROTOCOL = "docs/CORA_REAL_ARC_CAUSAL_PILOT_v1.md"
IMPLEMENTATION = (
    "cora_pilot/__init__.py", "cora_pilot/bundle.py", "cora_pilot/isolation.py", "cora_pilot/native.py",
    "cora_pilot/reasoner.py", "cora_pilot/evaluator.py",
    "scripts/pilot_v1_select.py", "scripts/pilot_v1_run.py", "scripts/pilot_v1_evaluate.py",
    "scripts/freeze_pilot_v1.py", "logs/pilot_v1/verify_pilot.py", "tests/test_pilot_v1.py",
    "records/pilot_v1/selection.json", "records/pilot_v1/dev_bundle.json", "records/pilot_v1/pilot_bundle.json",
    "records/REAL_ARC_PILOT_V1_DATA_AUDIT.md", "records/REAL_ARC_PILOT_V1_FEASIBILITY.md",
    "records/KAGGLE_2026_CONSTRAINTS.md",
    "cora_arc2026/v17_compiler.py", "cora_arc2026/v18_proposer.py", "cora_arc2026/v16_cfr.py",
    "cora_arc2026/v15_sel.py", "cora_arc2026/v14_loc.py", "cora_arc2026/v13_gen.py",
    "cora_arc2026/scorer_fit.py", "cora_v19/v19_repair.py",
    "outputs/tti/v18_frozen_d.json", "library.json",
    "harness/run_harness.py", "harness/pipeline_layer.py", "harness/geocat_layer.py",
    "harness/object_layer.py", "harness/near_solve_store.py", "harness/origin_classes.py", "harness/__init__.py")
EVALUATOR_ONLY = ("records/pilot_v1_evaluator/pilot_keymap.json",)
STATUSES = ("FROZEN_NOT_RUN",)


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def trees():
    out = {name: L.tree_digest(root) for name, root in L.dependency_roots(HERE).items()}
    for name in ("cora_v19", "cora_pilot", "harness"):
        out[name] = L.tree_digest(os.path.join(HERE, name))
    out["src/reasoning_project"] = L.tree_digest(os.path.join(HERE, "src", "reasoning_project"))
    return out


def constants():
    return {"dev_size": B.DEV_SIZE, "allowed_n": list(B.ALLOWED_N), "quota_sixths": B.QUOTA_SIXTHS,
            "order_prefix": B.ORDER_PREFIX, "gates": [list(g) for g in RS.GATES],
            "matched_s": [RS.MATCHED_MIN_S, RS.MATCHED_MAX_S], "support_min": RS.SUPPORT_MIN,
            "chain_flags": N.CHAIN_FLAGS, "run_error_max_share": EV.RUN_ERROR_MAX_SHARE,
            "sealed_count": EV.SEALED_COUNT}


def main():
    status = sys.argv[1] if len(sys.argv) > 1 else "FROZEN_NOT_RUN"
    bundle = json.load(open(os.path.join(HERE, "records", "pilot_v1", "pilot_bundle.json")))
    keymap = json.load(open(os.path.join(HERE, EVALUATOR_ONLY[0])))
    if keymap["bundle_sha256"] != hashlib.sha256(B.canonical_json(bundle)).hexdigest():
        raise SystemExit("key map and bundle disagree")
    man = {"status": status, "protocol_doc": PROTOCOL, "protocol_doc_sha256": sha(os.path.join(HERE, PROTOCOL)),
           "implementation_sha256": {p: sha(os.path.join(HERE, p)) for p in IMPLEMENTATION},
           "evaluator_only_sha256": {p: sha(os.path.join(HERE, p)) for p in EVALUATOR_ONLY},
           "dependency_tree_sha256": trees(), "runtime_versions": L.runtime_versions(),
           "k_identity": X.k_identity(), "repair_identity": R.repair_identity(),
           "data_sha256": {"challenges": B.CHALLENGES_SHA256, "solutions": B.SOLUTIONS_SHA256,
                           "sealed_v23": EV.SEALED_V23_SHA256, "sealed_arbitration": EV.SEALED_ARB_SHA256,
                           "library": N.LIBRARY_SHA256},
           "pilot": {"n": keymap["n"], "keys": sorted(bundle["tasks"]),
                     "bundle_sha256": keymap["bundle_sha256"]},
           "constants": constants()}
    with open(MANIFEST, "w") as fh:
        json.dump(man, fh, indent=1, sort_keys=True)
        fh.write("\n")
    digest = sha(MANIFEST)
    with open(MANIFEST + ".sha256", "w") as fh:
        fh.write(f"{digest}  pilot_v1_manifest.json\n")
    print(digest)


def freeze_problems(role="reasoner") -> list:
    """[] when the frozen state is intact. role "reasoner" (the coordinator)
    never opens the evaluator-only key map; role "evaluator" checks it too."""
    if not os.path.exists(MANIFEST):
        return ["no manifest"]
    man = json.load(open(MANIFEST))
    p = []
    if open(MANIFEST + ".sha256").read().split()[0] != sha(MANIFEST):
        p.append("manifest")
    if man.get("status") not in STATUSES:
        p.append(f"status {man.get('status')}")
    if sha(os.path.join(HERE, man["protocol_doc"])) != man["protocol_doc_sha256"]:
        p.append("protocol")
    for rel, d in man["implementation_sha256"].items():
        if not os.path.exists(os.path.join(HERE, rel)) or sha(os.path.join(HERE, rel)) != d:
            p.append(rel)
    if role == "evaluator":
        for rel, d in man["evaluator_only_sha256"].items():
            if sha(os.path.join(HERE, rel)) != d:
                p.append(rel)
    if trees() != man["dependency_tree_sha256"]:
        p.append("dependency trees")
    if L.runtime_versions() != man["runtime_versions"]:
        p.append("runtime_versions")
    if X.k_identity() != man["k_identity"]:
        p.append("k_identity")
    if R.repair_identity() != man["repair_identity"]:
        p.append("repair_identity")
    if constants() != man["constants"]:
        p.append("constants")
    return p


if __name__ == "__main__":
    main()
