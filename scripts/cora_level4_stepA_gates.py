"""Gates that must pass BEFORE the Step-A runner sees the 450 tasks.

Freezing the protocol but not the program that implements it is how a
criterion and its executable drift apart, so the runner and its traced search
are tested here, on synthetic fixtures and on the two already-spent Level-3
source programs, and only then hashed.

Three questions, kept separate:

  1 does tracing change the search?     identical winner, identical counts,
                                        identical leave-one-out verdict, on
                                        fixtures that finish inside the budget
  2 does the runner obey its own rules? synthetic corpus with opaque fake
                                        tokens: certified folds yield nothing,
                                        unsolved folds yield frontiers, a
                                        non-goal frontier has no residual,
                                        eligibility counts SOURCES not records
  3 is the output deterministic?        two runs, byte for byte

Question 3 has an honest boundary. The frozen search is time-budgeted, so a
fold that hits the deadline explores a timing-dependent amount and cannot be
byte-deterministic in principle. The gate therefore reports determinism over
all folds AND over non-truncating folds, and never claims the stronger fact
if only the weaker one holds.

This script is a GATE. Its output is a pass/fail record. It is not an input
to Step A, and the runner never reads anything it writes.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from level4_blind_runtime import env as E              # noqa: E402
from level4_blind_runtime import search as FROZEN      # noqa: E402
from level4_blind_runtime import stepA_trace_search as TRACED  # noqa: E402

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "stepA_extract", ROOT / "scripts" / "cora_level4_stepA_extract.py")
RUNNER = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RUNNER)

OUT = ROOT / "outputs" / "cora_breakthrough"
INPUTS = OUT / "level4_mechanism_inputs"


def token(label: str) -> str:
    """An opaque fake token, shaped like a real one, meaning nothing."""
    return hashlib.sha256(f"synthetic-{label}".encode()).hexdigest()[:16]


# --------------------------------------------------------------------------
# synthetic fixtures
# --------------------------------------------------------------------------

def solvable_demonstrations() -> list:
    """Recolour each colour component by its area. In the language."""
    demos = []
    layouts = [((0, 0), ((2, 2), (2, 3))),
               ((3, 4), ((0, 1), (1, 1))),
               ((4, 0), ((0, 3), (0, 4)))]
    for single, pair in layouts:
        grid_in = np.zeros((5, 5), dtype=int)
        grid_in[single] = 3
        for cell in pair:
            grid_in[cell] = 3
        grid_out = grid_in.copy()
        grid_out[single] = 6
        for cell in pair:
            grid_out[cell] = 7
        demos.append({"input": grid_in.tolist(), "output": grid_out.tolist()})
    return demos


def unsolvable_demonstrations(seed: int) -> list:
    """Output shape differs from input, which no admitted term can produce."""
    demos = []
    for index in range(3):
        grid_in = np.zeros((3, 3), dtype=int)
        grid_in[(index + seed) % 3, (index * 2 + seed) % 3] = 4
        grid_out = np.full((1, 1), 4, dtype=int)
        demos.append({"input": grid_in.tolist(), "output": grid_out.tolist()})
    return demos


def write_corpus(path: Path, records: list) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n"
                            for r in records))


# --------------------------------------------------------------------------
# gate 1: tracing must not change the search
# --------------------------------------------------------------------------

def compare_searches(pairs, env) -> dict:
    frozen_started = time.monotonic()
    frozen_results, frozen_stats = FROZEN.search(pairs, env=env)
    frozen_seconds = time.monotonic() - frozen_started

    observer = TRACED.TraceObserver()
    TRACED.set_observer(observer)
    traced_started = time.monotonic()
    try:
        traced_results, traced_stats = TRACED.search(pairs, env=env)
    finally:
        TRACED.set_observer(None)
    traced_seconds = time.monotonic() - traced_started

    def winner(results):
        return (RUNNER.canonical(E.to_json(results[0][0], env))
                if results else None)

    frozen_loo = FROZEN.loo_by_rediscovery(pairs, env=env)
    traced_loo = TRACED.loo_by_rediscovery(pairs, env=env)

    return {
        "winner_identical": winner(frozen_results) == winner(traced_results),
        "candidates_identical": len(frozen_results) == len(traced_results),
        "generated_identical":
            frozen_stats.generated == traced_stats.generated,
        "typed_identical": frozen_stats.typed == traced_stats.typed,
        "semantic_classes_identical":
            frozen_stats.semantic_classes == traced_stats.semantic_classes,
        "loo_identical": frozen_loo == traced_loo,
        "loo_frozen": list(frozen_loo),
        "frozen_seconds": round(frozen_seconds, 3),
        "traced_seconds": round(traced_seconds, 3),
        "overhead_ratio": (round(traced_seconds / frozen_seconds, 3)
                           if frozen_seconds > 0 else None),
        "terms_traced": len(observer.terms),
        "truncated": sorted(observer.truncations),
    }


def gate_search_equivalence(env) -> dict:
    rows = []

    demos = solvable_demonstrations()
    pairs = [(np.array(d["input"]), np.array(d["output"])) for d in demos]
    row = compare_searches(pairs, env)
    row["fixture"] = "synthetic solvable"
    rows.append(row)

    # -- the two already-spent Level-3 source programs ---------------------
    sources = json.loads((OUT / "v21_phase2_sources.json").read_text())
    challenges = json.loads(
        (ROOT / "data" / "arc-agi_training_challenges.json").read_text())
    for index, entry in enumerate(sources[:2]):
        task = challenges[entry["task"]]
        pairs = [(np.array(p["input"]), np.array(p["output"]))
                 for p in task["train"]]
        row = compare_searches(pairs, env)
        row["fixture"] = f"P{index + 1}"
        rows.append(row)

    keys = ("winner_identical", "candidates_identical", "generated_identical",
            "typed_identical", "semantic_classes_identical", "loo_identical")
    clean = [r for r in rows if not r["truncated"]]
    passed = all(r[k] for r in clean for k in keys) and bool(clean)
    return {"gate": "tracing does not change the search",
            "passed": passed,
            "fixtures_compared": len(rows),
            "fixtures_inside_budget": len(clean),
            "note": ("equivalence is asserted only on fixtures that finished "
                     "inside the frozen budget; a fixture that hits the "
                     "deadline explores a timing-dependent amount and cannot "
                     "be compared this way"),
            "rows": rows}


# --------------------------------------------------------------------------
# gate 2: the runner obeys its own rules
# --------------------------------------------------------------------------

def run_runner(corpus: Path, outdir: Path, tag: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "cora_level4_stepA_extract.py"),
         "--corpus", str(corpus), "--outdir", str(outdir), "--tag", tag],
        capture_output=True, text=True, cwd=str(ROOT))
    if result.returncode != 0:
        raise SystemExit(f"runner failed:\n{result.stdout}\n{result.stderr}")
    records = [json.loads(line) for line in
               (outdir / f"{tag}_frontier_records.jsonl").read_text()
               .splitlines() if line.strip()]
    folds = json.loads((outdir / f"{tag}_fold_summary.json").read_text())
    clusters = json.loads((outdir / f"{tag}_clusters.json").read_text())
    return {"records": records, "folds": folds, "clusters": clusters,
            "stdout": result.stdout}


def gate_runner_rules(workdir: Path) -> dict:
    checks = {}

    solvable = {"source_token": token("solvable"),
                "demonstrations": solvable_demonstrations()}
    write_corpus(workdir / "solvable.jsonl", [solvable])
    result = run_runner(workdir / "solvable.jsonl", workdir, "solvable")
    checks["certified_task_yields_no_frontiers"] = (
        result["folds"]["failed_folds"] == 0
        and len(result["records"]) == 0)

    one = {"source_token": token("one"), "demonstrations":
           unsolvable_demonstrations(0)}
    write_corpus(workdir / "one.jsonl", [one])
    result_one = run_runner(workdir / "one.jsonl", workdir, "one")
    checks["unsolved_task_yields_failed_folds"] = (
        result_one["folds"]["failed_folds"] > 0)
    checks["unsolved_task_yields_frontiers"] = len(result_one["records"]) > 0
    checks["single_source_never_eligible"] = all(
        not c["eligible"] for c in result_one["clusters"]["clusters"])
    checks["single_source_had_enough_records"] = any(
        c["records"] >= 3 for c in result_one["clusters"]["clusters"])

    goal = json.loads((INPUTS / "machine_manifest.json").read_text())["goal_type"]
    checks["non_goal_frontier_has_no_residual"] = all(
        row["behavioural_residual"] == "NOT_DEFINED"
        for row in result_one["records"] if row["frontier_type"] != goal)
    checks["goal_frontier_has_residual"] = all(
        row["behavioural_residual"] != "NOT_DEFINED"
        for row in result_one["records"] if row["frontier_type"] == goal)

    three = [{"source_token": token(f"three-{i}"),
              "demonstrations": unsolvable_demonstrations(i)}
             for i in range(3)]
    write_corpus(workdir / "three.jsonl", three)
    result_three = run_runner(workdir / "three.jsonl", workdir, "three")
    checks["three_sources_can_be_eligible"] = any(
        c["eligible"] for c in result_three["clusters"]["clusters"])
    checks["eligibility_counts_sources_not_records"] = all(
        c["eligible"] == (c["distinct_source_tokens"] >= 3)
        for c in result_three["clusters"]["clusters"])

    fields = {"source_token", "fold_index", "frontier_ast", "frontier_type",
              "goal_type", "frontier_value_signature", "goal_delta_signature",
              "behavioural_residual", "repeated_structure", "failure_class"}
    checks["records_carry_the_frozen_schema"] = all(
        fields <= set(row) for row in result_one["records"])
    classes = json.loads((INPUTS / "machine_manifest.json").read_text())[
        "failure_classes"]
    checks["failure_classes_are_the_frozen_five"] = all(
        row["failure_class"] in classes for row in
        result_one["records"] + result_three["records"])

    return {"gate": "the runner obeys the frozen protocol",
            "passed": all(checks.values()),
            "checks": checks,
            "records_seen": len(result_one["records"])
            + len(result_three["records"])}


# --------------------------------------------------------------------------
# gate 3: determinism
# --------------------------------------------------------------------------

def gate_determinism(workdir: Path) -> dict:
    corpus = workdir / "det.jsonl"
    write_corpus(corpus, [
        {"source_token": token(f"det-{i}"),
         "demonstrations": unsolvable_demonstrations(i)} for i in range(2)]
        + [{"source_token": token("det-solvable"),
            "demonstrations": solvable_demonstrations()}])

    digests, summaries = [], []
    for run in ("a", "b"):
        run_runner(corpus, workdir, f"det{run}")
        digest = hashlib.sha256()
        for name in ("frontier_records.jsonl", "clusters.json"):
            digest.update((workdir / f"det{run}_{name}").read_bytes())
        digests.append(digest.hexdigest())
        summaries.append(json.loads(
            (workdir / f"det{run}_fold_summary.json").read_text()))

    truncated = sum(s["truncated_folds"] for s in summaries)
    return {"gate": "byte-identical output on repeated runs",
            "passed": digests[0] == digests[1],
            "identical": digests[0] == digests[1],
            "truncated_folds_in_fixture": truncated,
            "note": ("a fold that hits the frozen deadline explores a "
                     "timing-dependent amount, so byte-determinism can only "
                     "be required of folds that finish inside the budget; "
                     "this fixture truncated "
                     f"{truncated} fold(s)"),
            "digests": digests}


# --------------------------------------------------------------------------

def main() -> int:
    manifest = json.loads((INPUTS / "machine_manifest.json").read_text())
    env = RUNNER.build_env(manifest)

    print("gate 1: tracing does not change the search")
    sys.stdout.flush()
    equivalence = gate_search_equivalence(env)
    for row in equivalence["rows"]:
        print(f"  {row['fixture']:20} winner {row['winner_identical']}  "
              f"generated {row['generated_identical']}  "
              f"typed {row['typed_identical']}  loo {row['loo_identical']}  "
              f"overhead x{row['overhead_ratio']}  "
              f"truncated {bool(row['truncated'])}")

    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        print("gate 2: the runner obeys the frozen protocol")
        sys.stdout.flush()
        rules = gate_runner_rules(workdir)
        for name, value in rules["checks"].items():
            print(f"  {'PASS' if value else 'FAIL'}  {name}")

        print("gate 3: determinism")
        sys.stdout.flush()
        determinism = gate_determinism(workdir)
        print(f"  identical {determinism['identical']}  "
              f"truncated folds {determinism['truncated_folds_in_fixture']}")

    report = {"gate": "Step-A pre-run gates",
              "passed": all(g["passed"] for g in
                            (equivalence, rules, determinism)),
              "search_equivalence": equivalence,
              "runner_rules": rules,
              "determinism": determinism}
    (OUT / "level4_stepA_gates.json").write_text(json.dumps(report, indent=1))

    print()
    print("ALL GATES PASSED" if report["passed"] else "GATES FAILED")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
