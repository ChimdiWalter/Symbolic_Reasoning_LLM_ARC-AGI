"""Freeze the real ARC growth-repair pilot v2 (manifest + .sha256).

  python scripts/freeze_pilot_v2.py            refuses if a manifest exists

Pins the protocol, every pilot implementation file, the frozen reach v1
mechanism and its development result, the selection and the bundle, the
harness, the native assets, every dependency tree, the data and sealed-record
checksums, runtime versions and constants. The evaluator-only key map is
pinned as well but checked only on the evaluator side
(freeze_problems("evaluator")), so the reasoner side never opens it.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_pilot import bundle as B                                # noqa: E402
from cora_pilot import evaluator as EV1                           # noqa: E402
from cora_pilot import native as N                                # noqa: E402
from cora_pilot2 import evaluator as EV                           # noqa: E402
from cora_reach import construct as CN                            # noqa: E402
from cora_reach import growth_ext as GE                           # noqa: E402
from cora_reach import measure as M                               # noqa: E402

MANIFEST = os.path.join(HERE, "outputs", "pilot_v2", "pilot_v2_manifest.json")
PROTOCOL = "docs/CORA_REAL_ARC_GROWTH_PILOT_v2.md"
IMPLEMENTATION = (
    "cora_pilot2/__init__.py", "cora_pilot2/reasoner.py", "cora_pilot2/evaluator.py",
    "scripts/pilot_v2_select.py", "scripts/pilot_v2_run.py", "scripts/pilot_v2_evaluate.py",
    "scripts/pilot_v2_verify.py", "scripts/pilot_v2_watch.sh", "scripts/freeze_pilot_v2.py",
    "tests/test_pilot_v2.py",
    "cora_pilot/__init__.py", "cora_pilot/bundle.py", "cora_pilot/isolation.py", "cora_pilot/native.py",
    "cora_pilot/evaluator.py",
    "cora_reach/__init__.py", "cora_reach/measure.py", "cora_reach/construct.py", "cora_reach/relations.py",
    "cora_reach/growth_ext.py", "cora_reach/bridge.py", "cora_reach/instances.py",
    "docs/CORA_REAL_TASK_REACH_DEV_v1.md", "docs/CORA_REAL_ARC_CAUSAL_PILOT_v1.md",
    "outputs/reach_v1/measure_manifest.json", "outputs/reach_v1/measure_summary.json",
    "records/REACH_V1_MEASURE_20261011.md",
    "records/pilot_v1/selection.json", "records/pilot_v2/pilot_bundle.json",
    "records/REAL_ARC_PILOT_V1_DATA_AUDIT.md",
    "library.json", "learned_verbs.json",
    "harness/run_harness.py", "harness/pipeline_layer.py", "harness/geocat_layer.py",
    "harness/object_layer.py", "harness/near_solve_store.py", "harness/origin_classes.py", "harness/__init__.py")
EVALUATOR_ONLY = ("records/pilot_v2_evaluator/pilot_keymap.json",)
STATUSES = ("FROZEN_NOT_RUN",)


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def trees():
    out = {name: L.tree_digest(root) for name, root in L.dependency_roots(HERE).items()}
    for name in ("cora_reach", "cora_pilot", "cora_pilot2", "harness"):
        out[name] = L.tree_digest(os.path.join(HERE, name))
    out["src/reasoning_project"] = L.tree_digest(os.path.join(HERE, "src", "reasoning_project"))
    return out


def constants():
    return {"dev_size": B.DEV_SIZE, "allowed_n": list(B.ALLOWED_N), "quota_sixths": B.QUOTA_SIXTHS,
            "order_prefix": B.ORDER_PREFIX, "gates": [list(g) for g in M.GATES],
            "measure": M.freeze_state(HERE)["limits"], "grammar": list(CN.GRAMMAR),
            "extension_identity": GE.identity(), "chain_flags": N.CHAIN_FLAGS,
            "run_error_max_share": EV.RUN_ERROR_MAX_SHARE, "sealed_count": EV1.SEALED_COUNT,
            "outcomes": list(EV.OUTCOMES), "causal_legs": list(EV.CAUSAL_LEGS)}


def main():
    if os.path.exists(MANIFEST):
        raise SystemExit("a manifest exists: the pilot is frozen")
    bundle = json.load(open(os.path.join(HERE, "records", "pilot_v2", "pilot_bundle.json")))
    keymap = json.load(open(os.path.join(HERE, EVALUATOR_ONLY[0])))
    if keymap["bundle_sha256"] != hashlib.sha256(B.canonical_json(bundle)).hexdigest():
        raise SystemExit("key map and bundle disagree")
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    man = {"status": "FROZEN_NOT_RUN", "protocol_doc": PROTOCOL,
           "protocol_doc_sha256": sha(os.path.join(HERE, PROTOCOL)),
           "implementation_sha256": {p: sha(os.path.join(HERE, p)) for p in IMPLEMENTATION},
           "evaluator_only_sha256": {p: sha(os.path.join(HERE, p)) for p in EVALUATOR_ONLY},
           "dependency_tree_sha256": trees(), "runtime_versions": L.runtime_versions(),
           "data_sha256": {"challenges": B.CHALLENGES_SHA256, "solutions": B.SOLUTIONS_SHA256,
                           "sealed_v23": EV1.SEALED_V23_SHA256, "sealed_arbitration": EV1.SEALED_ARB_SHA256,
                           "library": N.LIBRARY_SHA256, "learned_verbs": N.LEARNED_VERBS_SHA256},
           "pilot": {"n": keymap["n"], "keys": sorted(bundle["tasks"]),
                     "bundle_sha256": keymap["bundle_sha256"]},
           "constants": constants()}
    with open(MANIFEST, "w") as fh:
        json.dump(man, fh, indent=1, sort_keys=True)
        fh.write("\n")
    digest = sha(MANIFEST)
    with open(MANIFEST + ".sha256", "w") as fh:
        fh.write(f"{digest}  pilot_v2_manifest.json\n")
    print(json.dumps({"manifest_sha256": digest, "n": keymap["n"], "problems": freeze_problems("evaluator")}))


def freeze_problems(role="reasoner") -> list:
    """[] when the frozen state is intact. Role "reasoner" (the coordinator)
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
    if constants() != man["constants"]:
        p.append("constants")
    return p


if __name__ == "__main__":
    main()
