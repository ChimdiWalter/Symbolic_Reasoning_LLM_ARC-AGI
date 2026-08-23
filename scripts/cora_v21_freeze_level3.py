"""Freeze the Level-3 experiment BEFORE any non-provenance task is examined.

Writes a manifest pinning every hash, every search parameter, the macro
accounting policy, the scan pool and the exact witness criteria. After this
runs, nothing in the treatment, the baseline, the ranking, the budget or the
semantics may change. Only the experiment may proceed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning import meta_v21 as V  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_search as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"
SOURCES = ("7b6016b9", "83302e8f")


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    registry = json.loads((OUT / "v21_concept_registry.json").read_text())
    concept = list(registry.values())[0]
    manifest = {
        "experiment": "CORA V2.1 Level-3 causal transfer",
        "frozen": "2026-08-22",
        "hashes": {
            "semantic_contract": sha(OUT / "v2_1_semantic_contract_v2.json"),
            "runtime": sha(ROOT / "geocat_arc/object_reasoning/meta_v21.py"),
            "search": sha(ROOT / "geocat_arc/object_reasoning/meta_v21_search.py"),
            "environment_and_macro": sha(
                ROOT / "geocat_arc/object_reasoning/meta_v21_env.py"),
            "anti_unifier": sha(
                ROOT / "geocat_arc/object_reasoning/meta_v21_concept.py"),
            "concept_registry": sha(OUT / "v21_concept_registry.json"),
            "concept_schema": hashlib.sha256(
                json.dumps(concept["schema"], sort_keys=True).encode()
            ).hexdigest()[:16],
            "concept_source_programs": concept["source_program_sha256"],
        },
        "kernel_K": sorted(V.REGISTRY),
        "kernel_derivation": "operator closure of the two certified source programs",
        "treatment": "K + concept_0001, as an overlay; K is never mutated",
        "ablation": "the same environment with the overlay emptied, which is K",
        "search_parameters": {
            "MAX_DEPTH": S.MAX_DEPTH, "PER_TYPE_CAP": S.PER_TYPE_CAP,
            "MAX_CANDIDATES": S.MAX_CANDIDATES,
            "budget_seconds": S.budget_s(),
            "ranking": ["surface_cost", "surface_value_bound",
                        "stable_serialization"],
            "identical_function_for_both_arms": True,
        },
        "macro_accounting_policy": {
            "concept_cost": concept["cost"],
            "concept_surface_depth": 1,
            "expanded_core_reported_separately": True,
            "rationale": ("A macro expands entirely into K, so with unlimited "
                          "search it adds nothing. Its only possible effect is "
                          "compression under a bounded budget, which is why the "
                          "accounting is fixed here rather than after results "
                          "are seen."),
        },
        "concept_provenance": concept["provenance"],
        "scan_pool": ("every Experience-split task outside the concept's "
                      "provenance"),
        "criteria": {
            "3A_efficiency": [
                "task outside concept provenance",
                "both arms solve",
                "treatment winning SURFACE program contains the concept",
                "both arms pass leave-one-out by complete rediscovery",
                "treatment test prediction exactly correct",
                "treatment reduces a preregistered resource: typed candidates, "
                "seconds, or surface cost"],
            "3B_capability": [
                "task outside concept provenance",
                "K fails",
                "K + concept solves",
                "concept explicitly present in the winning surface program",
                "leave-one-out by complete rediscovery passes",
                "test prediction exactly correct",
                "ablation returns to failure"],
        },
        "claim_limit": ("A 3B witness would show that the set of solutions "
                        "REACHABLE UNDER THE FIXED BUDGET grew. It would NOT "
                        "show that the language can denote anything new, "
                        "because the concept expands into K."),
        "no_changes_after_this_point": ("no parameter, ranking rule, cost, "
                                        "depth, budget or semantic capability "
                                        "may change once the scan begins"),
    }
    path = OUT / "v21_level3_manifest.json"
    path.write_text(json.dumps(manifest, indent=1))
    print(json.dumps(manifest, indent=1))
    print("\nmanifest sha256:", sha(path)[:16])


if __name__ == "__main__":
    main()
