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
    "scripts/v17_acceptance.py", "scripts/run_v17_acceptance.sh", "scripts/freeze_v17.py",
    "records/ITEM2_V17_COMPILER_DESIGN.md", "records/ITEM2_V17_REVIEW_REQUEST.md",
    "records/ITEM2_V17_REVIEW_RESULT.md", "records/ITEM2_V17_ERRATUM_01.md",
    "logs/v17/fixtures.json", "logs/v17/findfix.py", "logs/v17/feas4.py",
    "logs/v17/dryrun_dev.py", "logs/v17/main_mock_test.py",
)
PREVIOUS = {"manifest_sha256": "418ee5c2f0e1ae30e43cdcf48de2c9faf1f55a5dfaaa566443f0b7437531bbb3",
            "frozen_commit": "d5b5e1b", "review_result_commit": "9195641"}


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def main():
    fast, engine = sys.argv[1], sys.argv[2]
    man = {
        "protocol": "CORA-TTI Item-2 v1.7 generic ConstructiveExtensionCompiler",
        "version": "1.7", "status": "FROZEN_AFTER_ERRATUM_01_NOT_ACCEPTANCE_TESTED",
        "erratum": {"record": "records/ITEM2_V17_ERRATUM_01.md", "previous": PREVIOUS},
        "environment": {"rule": "PYTHONHASHSEED=0 with hash randomization off; no ARC_* variable "
                                "except the K* pair, which kstar() sets itself; single-threaded "
                                "BLAS set by the acceptance script; one process at default CPU "
                                "priority, load recorded",
                        "kstar_env": X.KSTAR_ENV, "enforced_by": ["kstar()", "scripts/v17_acceptance.py",
                                                                 "scripts/run_v17_acceptance.sh"]},
        "external_file_sha256": {p: sha(p) for p in L.EXTERNAL_FILES},
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
                                      "S3": "zero residue (e's name anywhere in a K*-arm or 3x-arm winner), zero direct-execution disagreements for winners attributed to e, zero label anomalies (a top-level computed pattern carrying e's name that fails the structure test)",
                                      "S4": ">= 5 of 6 EXTENSION_NECESSARY_AND_USED with held-out exact",
                                      "S5": ">= 5 of 6 adaptive leave-one-out passed",
                                      "S6": "every task SEPARATED under the bounded witness test"},
                       "outcomes": ["COMPILER_ACCEPTED", "COMPILER_INTEGRATION_INCOMPLETE", "COMPILER_DEFECTIVE",
                                    "NO_VERDICT_FIXTURE_SHORTFALL", "NO_VERDICT_RUN_ERROR"],
                       "filter_reads": "the schema and the 7 training pairs only; never the held-out pair or the engine",
                       "max_seeds_searched": 2000,
                       "supplementary_not_gating": {"baseline_3x": "K* alone at 24 s budget per task: accepted, held-out exact, seconds",
                                                    "nested_uses": "e inside a wrapper other than a frame (not credited)",
                                                    "k_programs_fitted": "witness comparison-set size per task"},
                       "s5_caveat": "with the oracle proposer every fold recompiles the same schema and the filter already checked each fold's held-out pair with the scoped fitter, so S5 tests the L-leg machinery, not out-of-sample prediction; only S4's held-out pair is out of sample",
                       "run_once": "the launcher refuses if its pid record or the marker exists; the script refuses if its report, rows, start record or marker exist",
                       "recorded": "start record (environment, load, cpus), one row per finished task with per-arm seconds, events, programs and load"},
        "test_results_at_freeze": {"fast": fast, "engine": engine},
        "development_fixtures": {"seed_base": 810000000, "seeds": [810000100, 810004800]},
        "runtime_versions": L.runtime_versions(),
        "implementation_sha256": {rel: sha(os.path.join(HERE, rel)) for rel in IMPLEMENTATION},
        "dependency_tree_sha256": {n: L.tree_digest(r) for n, r in sorted(L.dependency_roots(HERE).items())},
        "claim_ceiling": "engineering capability only; not LEVEL 2 until an extension produced without the oracle pair is compiled and certified",
        "order_after_freeze": ["one adversarial review (done, records/ITEM2_V17_REVIEW_RESULT.md)",
                               "erratum 01 before the acceptance test (done)",
                               "scripts/run_v17_acceptance.sh once", "record the outcome",
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
