"""Confirmatory transfer run on the Promotion split.

Label, fixed before the run: Promotion was NEVER used for CORA design, but
its results were previously observed under the legacy engine (37 solved in
v23, 166 with stored near-solve records). This is therefore confirmatory
evidence on a NON-DESIGN split, not untouched prospective evidence.

Both arms execute symmetrically on every task. The baseline is never
conditioned on whether the treatment solved, which is the omission that made
the Experience run's witnesses uncertifiable until they were re-verified.

Nothing in the language, concept, search, ranking, cost, depth or budget is
modified. ``--fixtures`` runs the identical code path on already-used
Experience tasks so the runner can be tested before it is hashed and frozen.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning import meta_v21 as V  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_concept as C  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_env as E  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_search as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_concept():
    d = list(json.loads((OUT / "v21_concept_registry.json").read_text()).values())[0]
    return C.Concept(
        name=d["name"], schema=V.from_json(d["schema"]),
        slot_types={k: V.parse_type(v) for k, v in d["slot_types"].items()},
        provenance=tuple(d["provenance"]),
        source_hashes=tuple(d["source_program_sha256"]),
        result_type=V.parse_type(d["result_type"]), cost=d["cost"])


def run_arm(pairs, env, task, solutions, task_id):
    """One arm, run identically regardless of what the other arm did."""
    started = time.monotonic()
    results, stats = S.search(pairs, env=env)
    row = {"solved": bool(results),
           "typed_candidates": stats.typed,
           "seconds": round(time.monotonic() - started, 3)}
    if not results:
        return row, None
    ast = results[0][0]
    predicted = E.evaluate(ast, np.array(task["test"][0]["input"]), env)
    row["test_correct"] = bool(predicted is not None and np.array_equal(
        predicted, np.array(solutions[task_id][0])))
    row["surface"] = E.to_json(ast, env)
    row["accounting"] = E.accounting(ast, env)
    return row, ast


def evaluate_task(task_id, task, solutions, concept, envs):
    baseline_env, treatment_env = envs
    pairs = [(np.array(p["input"]), np.array(p["output"]))
             for p in task["train"]]
    if len(pairs) < 2:
        return None
    baseline, baseline_ast = run_arm(pairs, baseline_env, task, solutions, task_id)
    treatment, treatment_ast = run_arm(pairs, treatment_env, task, solutions,
                                       task_id)
    row = {"task": task_id, "baseline": baseline, "treatment": treatment}

    uses = bool(treatment_ast is not None and E.uses_concept(
        treatment_ast, treatment_env, concept.name))
    row["uses_concept"] = uses

    # leave-one-out is run whenever either arm solved, so a witness of either
    # class can be certified without a second pass
    if baseline["solved"] or treatment["solved"]:
        b_loo, folds = S.loo_by_rediscovery(pairs, env=baseline_env)
        t_loo, _ = S.loo_by_rediscovery(pairs, env=treatment_env)
        row["baseline_loo"] = f"{b_loo}/{folds}"
        row["treatment_loo"] = f"{t_loo}/{folds}"
        row["baseline_loo_full"] = (b_loo == folds and baseline["solved"])
        row["treatment_loo_full"] = (t_loo == folds and treatment["solved"])
    else:
        row["baseline_loo"] = row["treatment_loo"] = None
        row["baseline_loo_full"] = row["treatment_loo_full"] = False

    # frozen 3A: primary definition, byte-identical to the Experience run
    row["level_3a"] = bool(
        uses and baseline["solved"] and treatment["solved"]
        and row["baseline_loo_full"] and row["treatment_loo_full"]
        and treatment.get("test_correct")
        and baseline["typed_candidates"] > treatment["typed_candidates"])
    # secondary, stricter label, declared before the run
    row["level_3a_strict"] = bool(row["level_3a"] and baseline.get("test_correct"))
    # frozen 3B
    row["level_3b"] = bool(
        uses and not baseline["solved"] and treatment["solved"]
        and row["treatment_loo_full"] and treatment.get("test_correct"))
    row["outcome"] = ("both" if baseline["solved"] and treatment["solved"] else
                      "baseline_only" if baseline["solved"] else
                      "treatment_only" if treatment["solved"] else "neither")
    if baseline["solved"] and treatment["solved"]:
        row["d_typed_candidates"] = (baseline["typed_candidates"]
                                     - treatment["typed_candidates"])
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", action="store_true",
                        help="run on already-used Experience tasks to test "
                             "this runner before freezing it")
    args = parser.parse_args()

    concept = load_concept()
    baseline_env = E.BASE_ENV
    treatment_env = E.BASE_ENV.with_concept(concept)
    envs = (baseline_env, treatment_env)

    challenges = json.loads(
        (ROOT / "data" / "arc-agi_training_challenges.json").read_text())
    solutions = json.loads(
        (ROOT / "data" / "arc-agi_training_solutions.json").read_text())
    lockbox = json.loads((OUT.parent / "lockbox" / "manifest.json").read_text())
    tasks_meta = lockbox["tasks"]
    split = ({t["task_id"]: t["split"] for t in tasks_meta}
             if isinstance(tasks_meta, list)
             else {k: v["split"] for k, v in tasks_meta.items()})

    if args.fixtures:
        pool = ["00d62c1b", "a5313dff", "c0f76784", "12eac192"]
        label = "FIXTURES (already-used Experience tasks)"
        destination = OUT / "v21_promotion_runner_fixtures.json"
    else:
        manifest_path = OUT / "v21_promotion_manifest.json"
        if not manifest_path.exists():
            print("REFUSING TO RUN: no frozen Promotion manifest")
            return
        manifest = json.loads(manifest_path.read_text())
        drifted = [k for k, p in {
            "semantic_contract": OUT / "v2_1_semantic_contract_v2.json",
            "runtime": ROOT / "geocat_arc/object_reasoning/meta_v21.py",
            "search": ROOT / "geocat_arc/object_reasoning/meta_v21_search.py",
            "environment_and_macro": ROOT / "geocat_arc/object_reasoning/meta_v21_env.py",
            "anti_unifier": ROOT / "geocat_arc/object_reasoning/meta_v21_concept.py",
            "concept_registry": OUT / "v21_concept_registry.json",
            "promotion_runner": Path(__file__),
            "split_manifest": OUT.parent / "lockbox" / "manifest.json",
            "arc_challenges": ROOT / "data" / "arc-agi_training_challenges.json",
            "arc_solutions": ROOT / "data" / "arc-agi_training_solutions.json",
        }.items() if sha(p) != manifest["hashes"][k]]
        if drifted:
            print("REFUSING TO RUN: frozen artefacts drifted:", drifted)
            return
        pool = manifest["promotion_task_ids"]
        label = manifest["label"]
        destination = OUT / "v21_promotion_results.json"
        print("frozen Promotion manifest verified\n")

    print(f"{label}: {len(pool)} tasks\n")
    rows, counts = [], Counter()
    for task_id in pool:
        if not args.fixtures and split.get(task_id) != "promotion":
            continue
        row = evaluate_task(task_id, challenges[task_id], solutions, concept,
                            envs)
        if row is None:
            continue
        rows.append(row)
        counts[row["outcome"]] += 1
        if row["outcome"] != "neither":
            print(json.dumps({k: v for k, v in row.items()
                              if k not in ("baseline", "treatment")}),
                  flush=True)

    report = {"label": label, "pool_size": len(pool), "counts": dict(counts),
              "level_3a_witnesses": [r["task"] for r in rows if r["level_3a"]],
              "level_3a_strict_witnesses": [r["task"] for r in rows
                                            if r["level_3a_strict"]],
              "level_3b_witnesses": [r["task"] for r in rows if r["level_3b"]],
              "rows": rows}
    destination.write_text(json.dumps(report, indent=1, default=str))
    print("\nOUTCOMES", dict(counts))
    print("3A witnesses:", report["level_3a_witnesses"])
    print("3A-strict witnesses:", report["level_3a_strict_witnesses"])
    print("3B witnesses:", report["level_3b_witnesses"])


if __name__ == "__main__":
    main()
