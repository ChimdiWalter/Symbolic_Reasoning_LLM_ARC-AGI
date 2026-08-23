"""Step 1: certify the two candidate 3A witnesses against the FROZEN criterion.

The manifest required BOTH arms to pass leave-one-out by complete
rediscovery. The Phase-5 runner computed leave-one-out for the treatment
only, so the two candidates are not yet certified. This verifies the missing
half. It is verification of an existing criterion, never a change to it.

Read-only: no language, concept, search, ranking, cost, depth or budget is
modified, and the frozen hashes are re-checked before anything runs.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning import meta_v21 as V  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_concept as C  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_env as E  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_search as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"
CANDIDATES = ("00d62c1b", "a5313dff")


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_frozen(manifest):
    checks = {
        "semantic_contract": OUT / "v2_1_semantic_contract_v2.json",
        "runtime": ROOT / "geocat_arc/object_reasoning/meta_v21.py",
        "search": ROOT / "geocat_arc/object_reasoning/meta_v21_search.py",
        "environment_and_macro": ROOT / "geocat_arc/object_reasoning/meta_v21_env.py",
        "anti_unifier": ROOT / "geocat_arc/object_reasoning/meta_v21_concept.py",
        "concept_registry": OUT / "v21_concept_registry.json"}
    return [k for k, p in checks.items() if sha(p) != manifest["hashes"][k]]


def load_concept():
    d = list(json.loads((OUT / "v21_concept_registry.json").read_text()).values())[0]
    return C.Concept(
        name=d["name"], schema=V.from_json(d["schema"]),
        slot_types={k: V.parse_type(v) for k, v in d["slot_types"].items()},
        provenance=tuple(d["provenance"]),
        source_hashes=tuple(d["source_program_sha256"]),
        result_type=V.parse_type(d["result_type"]), cost=d["cost"])


def main():
    manifest = json.loads((OUT / "v21_level3_manifest.json").read_text())
    drifted = verify_frozen(manifest)
    if drifted:
        print("REFUSING TO RUN: frozen artefacts drifted:", drifted)
        return
    print("frozen manifest verified\n")

    concept = load_concept()
    baseline_env = E.BASE_ENV
    treatment_env = E.BASE_ENV.with_concept(concept)
    challenges = json.loads(
        (ROOT / "data" / "arc-agi_training_challenges.json").read_text())
    solutions = json.loads(
        (ROOT / "data" / "arc-agi_training_solutions.json").read_text())

    rows = []
    for task_id in CANDIDATES:
        task = challenges[task_id]
        pairs = [(np.array(p["input"]), np.array(p["output"]))
                 for p in task["train"]]
        baseline_loo, folds = S.loo_by_rediscovery(pairs, env=baseline_env)
        treatment_loo, _ = S.loo_by_rediscovery(pairs, env=treatment_env)

        baseline_results, baseline_stats = S.search(pairs, env=baseline_env)
        treatment_results, treatment_stats = S.search(pairs, env=treatment_env)
        uses = bool(treatment_results) and E.uses_concept(
            treatment_results[0][0], treatment_env, concept.name)
        predicted = (E.evaluate(treatment_results[0][0],
                                np.array(task["test"][0]["input"]),
                                treatment_env)
                     if treatment_results else None)
        test_correct = bool(predicted is not None and np.array_equal(
            predicted, np.array(solutions[task_id][0])))

        criterion = {
            "outside_provenance": task_id not in concept.provenance,
            "both_arms_solve": bool(baseline_results and treatment_results),
            "treatment_surface_uses_concept": uses,
            "baseline_loo": f"{baseline_loo}/{folds}",
            "treatment_loo": f"{treatment_loo}/{folds}",
            "both_arms_pass_loo": (baseline_loo == folds
                                   and treatment_loo == folds),
            "test_prediction_correct": test_correct,
            "d_typed_candidates": baseline_stats.typed - treatment_stats.typed,
            "resource_reduced": baseline_stats.typed > treatment_stats.typed}
        certified = all([criterion["outside_provenance"],
                         criterion["both_arms_solve"],
                         criterion["treatment_surface_uses_concept"],
                         criterion["both_arms_pass_loo"],
                         criterion["test_prediction_correct"],
                         criterion["resource_reduced"]])
        row = {"task": task_id, "verdict": "CERTIFIED" if certified
               else "REJECTED", "criterion": criterion}
        rows.append(row)
        print(json.dumps(row, indent=1), flush=True)

    (OUT / "v21_level3a_certification.json").write_text(
        json.dumps({"manifest_sha256": sha(OUT / "v21_level3_manifest.json")[:16],
                    "rows": rows}, indent=1))
    certified = [r for r in rows if r["verdict"] == "CERTIFIED"]
    print(f"\nCERTIFIED 3A witnesses: {len(certified)} of {len(CANDIDATES)}")


if __name__ == "__main__":
    main()
