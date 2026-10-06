"""Item-2 v1.8: write the frozen no-oracle proposer manifest and its hash.

    freeze_v18.py <tests_fast_summary> <tests_engine_summary>
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "scripts"))

from cora_arc2026 import v14_loc as L                             # noqa: E402
from cora_arc2026 import v17_compiler as X                        # noqa: E402
from cora_arc2026 import v18_proposer as P                        # noqa: E402
import v18_corpus as CORPUS                                       # noqa: E402
import v18_prospective as PROS                                    # noqa: E402

PROTOCOL = "docs/CORA_TTI_NO_ORACLE_PROPOSER_v1.8.md"
MANIFEST = os.path.join(HERE, "outputs", "tti", "no_oracle_proposer_v18_manifest.json")
V17_COMPILER_SHA256 = "04c6b3a19b9645cdfd983e2733e377b8b342e11a4c09b209f3dddb5868515152"
FROZEN_D_SHA256 = "b0ae3eca87e18116b3a4cbbc693b1a540c474e35bec82ca7e2b6c37e3f576e39"
IMPLEMENTATION = (
    "cora_arc2026/v18_proposer.py", "cora_arc2026/v17_compiler.py", "cora_arc2026/v16_cfr.py",
    "cora_arc2026/v15_sel.py", "cora_arc2026/v14_loc.py", "cora_arc2026/v13_gen.py",
    "cora_arc2026/scorer_fit.py", "cora_arc2026/vendor/tfg_extractor.py",
    "tests/test_v18_proposer.py", "tests/test_v17_compiler.py", "tests/conftest.py",
    "scripts/v18_corpus.py", "scripts/v18_dev_audit.py", "scripts/v18_build_exclusion.py",
    "scripts/v18_prospective.py", "scripts/v18_freeze_d.py", "scripts/v18_feasibility.py",
    "scripts/freeze_v18.py",
    "records/ITEM2_V18_PROPOSER_DESIGN.md", "records/ITEM2_V18_DEVELOPMENT_RESULT.md",
    "records/ITEM2_V18_FEASIBILITY.md", "records/ITEM2_V18_REVIEW_REQUEST.md",
    "records/ITEM2_V18_REVIEW_RESULT.md", "records/ITEM2_V18_ERRATUM_01.md",
    "scripts/v18_dev_controls.py", "outputs/tti/v18_dev_controls.json",
    "outputs/tti/v18_frozen_d.json", "outputs/tti/v18_prospective_exclusion.json",
    "outputs/tti/v18_dev_audit.json", "outputs/tti/v18_dev_rows.jsonl",
    "outputs/tti/v18_feasibility.json", "logs/v18/dedup_heldout_check.py",
    "logs/v18/dedup_heldout_check.json",
)


def sha(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def main():
    fast, engine = sys.argv[1], sys.argv[2]
    if sha(os.path.join(HERE, "cora_arc2026", "v17_compiler.py")) != V17_COMPILER_SHA256:
        raise SystemExit("the v1.7 compiler changed; it is frozen infrastructure")
    if sha(P.FROZEN_D) != FROZEN_D_SHA256:
        raise SystemExit("the frozen D changed")
    if PROS.N_TASKS is None or PROS.W_MIN is None:
        raise SystemExit("prospective thresholds unset")
    with open(os.path.join(HERE, "outputs", "tti", "v18_prospective_exclusion.json")) as handle:
        excl = json.load(handle)
    man = {
        "protocol": "CORA-TTI Item-2 v1.8 no-oracle extension proposer",
        "version": "1.8", "status": "FROZEN_AFTER_ERRATUM_01_NOT_PROSPECTIVELY_TESTED",
        "erratum": {"record": "records/ITEM2_V18_ERRATUM_01.md",
                    "review": "records/ITEM2_V18_REVIEW_RESULT.md",
                    "previous": {"frozen_commit": "e7afc0f",
                                 "manifest_sha256": "bd657faa12225d775e028a07e6208345c37b518f6c4c0f07ce518bdc9c8e8f7a"}},
        "protocol_doc": PROTOCOL, "protocol_doc_sha256": sha(os.path.join(HERE, PROTOCOL)),
        "parent": {"v17_result_commit": "2299c95", "v17_outcome": "COMPILER_ACCEPTED",
                   "v17_manifest_sha256": "a66e149cf7d971ae4166033c95cfe2567a9be5ea160c792b9abecca9d08b1f29",
                   "v16_classification": "PURE_RULE_WITH_DEMONSTRATION_FALLBACK_GENERALIZES",
                   "claim": "LEVEL 1, hybrid"},
        "proposer_version": P.VERSION, "proposer_sha256": P.proposer_sha256(),
        "input_format": P.FORMAT_INPUT, "limits": P.LIMITS, "arms": list(P.ARMS),
        "selection_levels": list(P.SELECTION_LEVELS), "failure_classes": list(P.FAILURE_CLASSES),
        "infrastructure_classes": sorted(P.INFRASTRUCTURE), "forbidden_key_words": list(P.FORBIDDEN_WORDS),
        "frozen_d_sha256": FROZEN_D_SHA256, "v17_compiler_sha256": V17_COMPILER_SHA256,
        "k_identity": X.k_identity(), "kstar_env": X.KSTAR_ENV,
        "environment": {"rule": "PYTHONHASHSEED=0 with hash randomization off; no ARC_* variable except the "
                                "K* pair, which kstar() sets; single-threaded BLAS set by the scripts",
                        "enforced_by": ["kstar()", "scripts/v18_prospective.py"]},
        "development": {"seed_base": CORPUS.DEV_BASE, "tasks": 40, "engine_tasks": 8,
                        "record": "records/ITEM2_V18_DEVELOPMENT_RESULT.md",
                        "audit_sha256": sha(os.path.join(HERE, "outputs", "tti", "v18_dev_audit.json"))},
        "prospective": {"script": "scripts/v18_prospective.py", "seed_base": CORPUS.PROSPECTIVE_BASE,
                        "tasks": PROS.N_TASKS, "witnesses_required": PROS.W_MIN, "alpha": PROS.ALPHA,
                        "g1_controls": list(PROS.G1_CONTROLS), "sanity_arms": list(PROS.SANITY_ARMS),
                        "witness_A": f"K* alone at {PROS.BASELINE_3X_BUDGET_S} s does not reproduce the held-out output",
                        "blind_order_sha256": hashlib.sha256(json.dumps(list(P.BLIND_ORDER)).encode()).hexdigest(),
                        "outcomes": list(PROS.OUTCOMES),
                        "exclusion": {"file": "outputs/tti/v18_prospective_exclusion.json",
                                      "target_digests": excl["total"], "sources": excl["sources"]}},
        "test_results_at_freeze": {"fast": fast, "engine": engine},
        "runtime_versions": L.runtime_versions(),
        "implementation_sha256": {rel: sha(os.path.join(HERE, rel)) for rel in IMPLEMENTATION},
        "dependency_tree_sha256": {n: L.tree_digest(r) for n, r in sorted(L.dependency_roots(HERE).items())},
        "external_file_sha256": {p: sha(p) for p in L.EXTERNAL_FILES},
        "claim_ceiling": "before the prospective test: engineering evidence on development data only; a "
                         "prospective acceptance would be LEVEL 2 for the synthetic domain, never a real ARC "
                         "result; LEVEL 3 needs a real ARC B/P/U/L/T/A witness",
        "order_after_freeze": ["one adversarial review", "errata before any prospective execution",
                               "next stage: the closed-loop causal pilot, whose first frozen step is "
                               "scripts/v18_prospective.py run once"],
    }
    with open(MANIFEST, "w") as handle:
        handle.write(json.dumps(man, indent=1, sort_keys=True) + "\n")
    digest = sha(MANIFEST)
    with open(MANIFEST + ".sha256", "w") as handle:
        handle.write(f"{digest}  {os.path.basename(MANIFEST)}\n")
    print(json.dumps({"manifest_sha256": digest, "protocol_sha256": man["protocol_doc_sha256"],
                      "proposer_sha256": man["proposer_sha256"], "k_identity": man["k_identity"]}))


if __name__ == "__main__":
    main()
