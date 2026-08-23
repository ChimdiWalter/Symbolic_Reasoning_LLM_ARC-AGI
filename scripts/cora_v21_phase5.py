"""Phase 5: K versus K + C1 versus ablation, on tasks outside provenance.

The first prospective evidence in this line of work. Both arms call the same
search function; only the language environment differs. Criteria were frozen
in v21_level3_manifest.json before any task here was examined.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning import meta_v21 as V  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_concept as C  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_env as E  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_search as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"


def load_concept():
    registry = json.loads((OUT / "v21_concept_registry.json").read_text())
    d = list(registry.values())[0]
    return C.Concept(
        name=d["name"], schema=V.from_json(d["schema"]),
        slot_types={k: V.parse_type(v) for k, v in d["slot_types"].items()},
        provenance=tuple(d["provenance"]),
        source_hashes=tuple(d["source_program_sha256"]),
        result_type=V.parse_type(d["result_type"]), cost=d["cost"])


def verify_frozen(manifest):
    """Refuse to run if anything the manifest pinned has moved."""
    checks = {
        "semantic_contract": OUT / "v2_1_semantic_contract_v2.json",
        "runtime": ROOT / "geocat_arc/object_reasoning/meta_v21.py",
        "search": ROOT / "geocat_arc/object_reasoning/meta_v21_search.py",
        "environment_and_macro": ROOT / "geocat_arc/object_reasoning/meta_v21_env.py",
        "anti_unifier": ROOT / "geocat_arc/object_reasoning/meta_v21_concept.py",
        "concept_registry": OUT / "v21_concept_registry.json",
    }
    drifted = []
    for key, path in checks.items():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != manifest["hashes"][key]:
            drifted.append(key)
    return drifted


def run_arm(pairs, env):
    started = time.monotonic()
    results, stats = S.search(pairs, env=env)
    row = {"solved": bool(results), "seconds": round(time.monotonic() - started, 3),
           "typed_candidates": stats.typed, "generated": stats.generated}
    if results:
        ast = results[0][0]
        row.update({"surface": E.to_json(ast, env),
                    "accounting": E.accounting(ast, env),
                    "ops": sorted(set(E.concepts_used(ast, env)))})
        row["_ast"] = ast
    return row


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
    ablation_env = treatment_env.without_concepts()

    challenges = json.loads(
        (ROOT / "data" / "arc-agi_training_challenges.json").read_text())
    solutions = json.loads(
        (ROOT / "data" / "arc-agi_training_solutions.json").read_text())
    lockbox = json.loads((OUT.parent / "lockbox" / "manifest.json").read_text())
    tasks = lockbox["tasks"]
    split = ({t["task_id"]: t["split"] for t in tasks} if isinstance(tasks, list)
             else {k: v["split"] for k, v in tasks.items()})
    pool = sorted(t for t, s in split.items()
                  if s == "experience" and t not in concept.provenance)
    print(f"scan pool: {len(pool)} Experience tasks outside provenance\n")

    witnesses, rows = [], []
    for task_id in pool:
        task = challenges[task_id]
        pairs = [(np.array(p["input"]), np.array(p["output"]))
                 for p in task["train"]]
        if len(pairs) < 2:
            continue
        treatment = run_arm(pairs, treatment_env)
        if not treatment["solved"]:
            continue                      # nothing to compare
        baseline = run_arm(pairs, baseline_env)
        ablation = run_arm(pairs, ablation_env)

        ast = treatment.pop("_ast")
        baseline.pop("_ast", None)
        ablation.pop("_ast", None)
        uses = E.uses_concept(ast, treatment_env, concept.name)
        loo_passed, folds = S.loo_by_rediscovery(pairs, env=treatment_env)
        predicted = E.evaluate(ast, np.array(task["test"][0]["input"]),
                               treatment_env)
        test_correct = bool(predicted is not None and np.array_equal(
            predicted, np.array(solutions[task_id][0])))

        row = {"task": task_id, "baseline": baseline, "treatment": treatment,
               "ablation": ablation, "uses_concept": uses,
               "loo": f"{loo_passed}/{folds}", "test_correct": test_correct}
        capability = bool(uses and not baseline["solved"]
                          and not ablation["solved"] and loo_passed == folds
                          and test_correct)
        efficiency = None
        if uses and baseline["solved"] and loo_passed == folds and test_correct:
            efficiency = {
                "d_typed_candidates": baseline["typed_candidates"]
                - treatment["typed_candidates"],
                "d_seconds": round(baseline["seconds"] - treatment["seconds"], 3),
                "d_surface_cost": (baseline.get("accounting", {}).get("surface_cost", 0)
                                   - treatment["accounting"]["surface_cost"])}
        row["level_3b_capability"] = capability
        row["level_3a_efficiency"] = efficiency
        rows.append(row)
        if capability or efficiency:
            witnesses.append(row)
        print(json.dumps({k: v for k, v in row.items()
                          if k not in ("baseline", "treatment", "ablation")}),
              flush=True)

    report = {"manifest_sha256": hashlib.sha256(
        (OUT / "v21_level3_manifest.json").read_bytes()).hexdigest()[:16],
        "pool_size": len(pool), "rows": rows}
    (OUT / "v21_level3_results.json").write_text(
        json.dumps(report, indent=1, default=str))
    capability = [r for r in rows if r["level_3b_capability"]]
    efficiency = [r for r in rows if r["level_3a_efficiency"]]
    print(f"\ntreatment solved: {len(rows)} of {len(pool)}")
    print(f"LEVEL 3B capability witnesses: {len(capability)}")
    print(f"LEVEL 3A efficiency witnesses: {len(efficiency)}")


if __name__ == "__main__":
    main()
