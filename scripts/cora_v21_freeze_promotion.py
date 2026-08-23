"""Freeze the Promotion confirmatory manifest, runner hash included.

The Experience manifest froze the criteria but not the runner, and that is
exactly where the baseline-leave-one-out omission slipped in. Here the
order is reversed: the runner was written and tested first, and its hash is
pinned alongside everything else before a single Promotion task is examined.
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


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    lockbox = json.loads((OUT.parent / "lockbox" / "manifest.json").read_text())
    tasks = lockbox["tasks"]
    split = ({t["task_id"]: t["split"] for t in tasks} if isinstance(tasks, list)
             else {k: v["split"] for k, v in tasks.items()})
    promotion = sorted(t for t, s in split.items() if s == "promotion")
    concept = list(json.loads(
        (OUT / "v21_concept_registry.json").read_text()).values())[0]

    manifest = {
        "experiment": ("CORA V2.1 confirmatory transfer on a non-design split "
                       "previously scored by the legacy engine"),
        "frozen": "2026-08-22",
        "label": ("CONFIRMATORY_NON_DESIGN: Promotion, legacy-scored, never "
                  "used to build K or learn C1"),
        "evaluation_status": "CONFIRMATORY_NON_DESIGN",
        "prior_exposure": {
            "legacy_v22_v23_scoring": True,
            "promotion_tasks_in_v23_solved_set": 37,
            "promotion_tasks_in_v22_solved_set": 34,
            "near_solve_records": "166 of 200",
            "used_in_cora_expression_trace": False,
            "used_in_cora_trigger_audit": False,
            "used_to_construct_K": False,
            "used_to_learn_C1": False},
        "claim_limit": ("confirms transfer outside the CORA design split; does "
                        "NOT constitute untouched prospective evaluation, and "
                        "must never be described as untouched, pristine, "
                        "fully prospective, or lockbox validation"),
        "hashes": {
            "semantic_contract": sha(OUT / "v2_1_semantic_contract_v2.json"),
            "runtime": sha(ROOT / "geocat_arc/object_reasoning/meta_v21.py"),
            "search": sha(ROOT / "geocat_arc/object_reasoning/meta_v21_search.py"),
            "environment_and_macro": sha(
                ROOT / "geocat_arc/object_reasoning/meta_v21_env.py"),
            "anti_unifier": sha(
                ROOT / "geocat_arc/object_reasoning/meta_v21_concept.py"),
            "concept_registry": sha(OUT / "v21_concept_registry.json"),
            "promotion_runner": sha(
                ROOT / "scripts/cora_v21_promotion_runner.py"),
            "split_manifest": sha(OUT.parent / "lockbox" / "manifest.json"),
            "arc_challenges": sha(
                ROOT / "data" / "arc-agi_training_challenges.json"),
            "arc_solutions": sha(
                ROOT / "data" / "arc-agi_training_solutions.json")},
        "runner_validation": ("tested on already-spent Experience fixtures "
                              "before hashing; reproduced both certified "
                              "witnesses and correctly rejected c0f76784 on "
                              "leave-one-out and 12eac192 on concept use"),
        "kernel_K": sorted(V.REGISTRY),
        "concept": {"name": concept["name"], "cost": concept["cost"],
                    "arg_types": concept["arg_types"],
                    "result_type": concept["result_type"],
                    "provenance": concept["provenance"]},
        "unchanged_from_experience_run": [
            "kernel K", "concept schema", "concept cost", "macro depth",
            "MAX_DEPTH", "PER_TYPE_CAP", "MAX_CANDIDATES", "budget",
            "ranking", "slot learner", "leave-one-out procedure",
            "search implementation", "3A definition", "3B definition"],
        "only_change": "scan pool: Experience -> Promotion",
        "search_parameters": {"MAX_DEPTH": S.MAX_DEPTH,
                              "PER_TYPE_CAP": S.PER_TYPE_CAP,
                              "MAX_CANDIDATES": S.MAX_CANDIDATES,
                              "budget_seconds": S.budget_s()},
        "promotion_task_ids": promotion,
        "promotion_task_count": len(promotion),
        "primary_measure": ("typed candidate programs examined before the "
                            "accepted exact-fit solution; timing is "
                            "descriptive only and surface-cost compression is "
                            "true by construction, so neither is independent "
                            "evidence"),
        "all_arms_symmetric": ("both arms run on every task; the baseline is "
                               "never conditioned on treatment success"),
        "frozen_interpretations": {
            "certified_3A": ("the learned abstraction's bounded-search "
                             "efficiency benefit replicated on a separate "
                             "non-design split, which was not used to build "
                             "the V2.1 language or concept; the split had "
                             "been legacy-scored, so this is not untouched "
                             "prospective evaluation"),
            "certified_3B": ("the learned abstraction made a solution "
                             "reachable under the frozen bounded-search "
                             "regime on a separate non-design split; still "
                             "not denotational expressivity"),
            "concept_used_no_witness": ("the abstraction had coverage but did "
                                        "not yield certified transfer; no "
                                        "tweaking follows"),
            "concept_never_used": ("no confirmatory test occurred because the "
                                   "concept had zero coverage; this is NOT "
                                   "evidence that Level 3A was false"),
            "baseline_only_cases": ("negative interference; to be reported "
                                    "prominently, never hidden behind a net "
                                    "average"),
            "zero_witnesses": ("accept the null; do not repair C1 and rerun "
                               "Promotion")},
        "lockbox": "stays closed regardless of the outcome",
        "no_changes_after_this_point": True,
    }
    path = OUT / "v21_promotion_manifest.json"
    path.write_text(json.dumps(manifest, indent=1))
    print("Promotion manifest frozen")
    print("  runner hash:", manifest["hashes"]["promotion_runner"][:16])
    print("  tasks:", manifest["promotion_task_count"])
    print("  manifest sha256:", sha(path)[:16])


if __name__ == "__main__":
    main()
