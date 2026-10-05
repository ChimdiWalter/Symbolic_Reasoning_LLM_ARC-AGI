"""Item-2 v1.7: write the frozen compiler manifest and its hash file.

    freeze_v17.py <tests_fast_summary> <tests_engine_summary>
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_arc2026 import v17_compiler as X                        # noqa: E402

PROTOCOL = "docs/CORA_TTI_CONSTRUCTIVE_EXTENSION_COMPILER_v1.7.md"
MANIFEST = os.path.join(HERE, "outputs", "tti", "constructive_extension_compiler_v17_manifest.json")
IMPLEMENTATION = (
    "cora_arc2026/v17_compiler.py", "cora_arc2026/v15_sel.py", "cora_arc2026/v14_loc.py",
    "cora_arc2026/v13_gen.py", "tests/test_v17_compiler.py", "tests/conftest.py",
    "scripts/v17_acceptance.py", "scripts/freeze_v17.py",
    "records/ITEM2_V17_COMPILER_DESIGN.md", "logs/v17/fixtures.json",
    "logs/v17/findfix.py", "logs/v17/feas4.py",
)


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def main():
    fast, engine = sys.argv[1], sys.argv[2]
    man = {
        "protocol": "CORA-TTI Item-2 v1.7 generic ConstructiveExtensionCompiler",
        "version": "1.7", "status": "FROZEN_NOT_ACCEPTANCE_TESTED",
        "protocol_doc": PROTOCOL, "protocol_doc_sha256": sha(os.path.join(HERE, PROTOCOL)),
        "parent": {"v16_result_commit": "27078d1",
                   "v16_classification": "PURE_RULE_WITH_DEMONSTRATION_FALLBACK_GENERALIZES",
                   "v16_claim": "LEVEL 1, hybrid"},
        "compiler_version": X.COMPILER_VERSION, "compiler_sha256": X.compiler_sha256(),
        "k_identity": X.k_identity(), "kstar_rules": list(X.KSTAR_RULES), "kstar_env": X.KSTAR_ENV,
        "failure_classes": list(X.FAILURE_CLASSES), "limits": X.LIMITS,
        "input_keys": sorted(X.INPUT_KEYS), "provenance_keys": sorted(X.PROVENANCE_KEYS),
        "acceptance": {"script": "scripts/v17_acceptance.py", "seed_base": 830000000, "tasks": 6,
                       "conditions": {"S1": "all compile; deterministic bytes; identical reload; fresh-process identical (first task)",
                                      "S2": "no restoration failure; final snapshot equals initial",
                                      "S3": "zero residue (no K*-arm winner carries e's name) and zero direct-execution disagreements for winners attributed to e",
                                      "S4": ">= 5 of 6 EXTENSION_NECESSARY_AND_USED with held-out exact",
                                      "S5": ">= 5 of 6 adaptive leave-one-out passed",
                                      "S6": "every task SEPARATED under the bounded witness test"},
                       "outcomes": ["COMPILER_ACCEPTED", "COMPILER_INTEGRATION_INCOMPLETE", "COMPILER_DEFECTIVE",
                                    "NO_VERDICT_FIXTURE_SHORTFALL"],
                       "filter_reads": "the schema and the 7 training pairs only; never the held-out pair or the engine",
                       "max_seeds_searched": 2000},
        "test_results_at_freeze": {"fast": fast, "engine": engine},
        "development_fixtures": {"seed_base": 810000000, "seeds": [810000100, 810004800]},
        "runtime_versions": L.runtime_versions(),
        "implementation_sha256": {rel: sha(os.path.join(HERE, rel)) for rel in IMPLEMENTATION},
        "dependency_tree_sha256": {n: L.tree_digest(r) for n, r in sorted(L.dependency_roots(HERE).items())},
        "claim_ceiling": "engineering capability only; not LEVEL 2 until an extension produced without the oracle pair is compiled and certified",
        "order_after_freeze": ["one adversarial review", "errata before the acceptance test",
                               "scripts/v17_acceptance.py once", "record the outcome",
                               "next stage: no-oracle extension proposer (not in this block)"],
    }
    with open(MANIFEST, "w") as handle:
        handle.write(json.dumps(man, indent=1, sort_keys=True) + "\n")
    digest = sha(MANIFEST)
    with open(MANIFEST + ".sha256", "w") as handle:
        handle.write(f"{digest}  {os.path.basename(MANIFEST)}\n")
    print(json.dumps({"manifest_sha256": digest, "protocol_sha256": man["protocol_doc_sha256"],
                      "compiler_sha256": man["compiler_sha256"], "k_identity": man["k_identity"]}))


if __name__ == "__main__":
    main()
