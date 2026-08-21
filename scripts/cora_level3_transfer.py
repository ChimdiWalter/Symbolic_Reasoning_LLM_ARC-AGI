"""Level-3 experiment: does a learned concept change future reasoning?

Stage 1 lets two source tasks produce a concept by anti-unification.
Stage 2 asks whether that concept enables a task that played no part in
creating it, under three conditions at identical budgets:

    without the concept        the learner as it was
    with the concept           the same learner, concept available
    ablated                    the concept removed again

A witness counts only when the middle condition solves what the outer two
cannot, the winning program instantiates the concept, and the ordinary gate
accepted it.  Hypotheses, seconds and program size are recorded for each
condition so the effect can be reported as capability or as compression --
whichever it actually is.

Experience split only; Promotion and Lockbox tasks are never opened here.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning import meta_induction as MI  # noqa: E402
from geocat_arc.object_reasoning.concept_registry import (  # noqa: E402
    ConceptLibrary,
    learn_concepts,
)
from geocat_arc.object_reasoning.inducer import (  # noqa: E402
    InductionConfig,
    induce_program,
)
from geocat_arc.object_reasoning.types import to_grid_pairs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"
SOURCES = ("7b6016b9", "83302e8f")


def load(split_wanted="experience"):
    challenges = json.loads(
        (ROOT / "data" / "arc-agi_training_challenges.json").read_text())
    solutions = json.loads(
        (ROOT / "data" / "arc-agi_training_solutions.json").read_text())
    manifest = json.loads((ROOT / "outputs" / "lockbox" / "manifest.json").read_text())
    tasks = manifest["tasks"]
    split = ({t["task_id"]: t["split"] for t in tasks} if isinstance(tasks, list)
             else {k: v["split"] for k, v in tasks.items()})
    ids = sorted(t for t, s in split.items() if s == split_wanted)
    return challenges, solutions, ids


def pairs_of(task):
    return [(np.array(p["input"]), np.array(p["output"])) for p in task["train"]]


def discover(task):
    """Run the ordinary discovery on a task's demonstrations."""
    asts, stats = MI.search(pairs_of(task))
    return (asts[0] if asts else None), stats


def attempt(task, concepts, budget_s: float):
    """Induce with a given concept set; return acceptance, cost and the
    EXACT winning program (serialized), so the test prediction is made by
    the program that was accepted rather than by a fresh re-induction."""
    original = MI.induce_computed_candidates

    def patched(train_pairs, deadline=None, concepts_=tuple(concepts), **kw):
        return original(train_pairs, deadline=deadline, concepts=concepts_)

    MI.induce_computed_candidates = patched
    try:
        started = time.monotonic()
        result = induce_program(to_grid_pairs(pairs_of(task)),
                                InductionConfig(budget_s=budget_s))
        program_json = (result.program.to_dict()
                        if result.accepted and result.program is not None
                        else None)
        return {"accepted": bool(result.accepted),
                "class": type(result.program).__name__ if result.program else None,
                "concept": getattr(result.program, "concept", None),
                "concepts_used": list(getattr(result.program,
                                              "grammar_concepts_used", []) or []),
                "hypotheses": int(result.hypotheses_enumerated or 0),
                "seconds": round(time.monotonic() - started, 2),
                "size": (result.program.expression_size
                         if result.program is not None
                         and hasattr(result.program, "expression_size") else None),
                "program": program_json}
    finally:
        MI.induce_computed_candidates = original


def test_correct_of(row, task, solutions, tid):
    """Render the ACCEPTED program on the test input -- no re-induction."""
    from geocat_arc.object_reasoning.actions import program_apply_fn
    from geocat_arc.object_reasoning.types import program_from_dict
    if not row.get("program"):
        return None
    try:
        program = program_from_dict(json.loads(json.dumps(row["program"])))
        got = program_apply_fn(program)(np.array(task["test"][0]["input"]))
        return bool(np.array_equal(got, np.array(solutions[tid][0])))
    except Exception as exc:
        return f"error:{exc}"


def uses_concept(row, concept_names) -> bool:
    """Did the winning program actually instantiate one of these concepts?"""
    if row.get("concept") in concept_names:
        return True
    return any(name in (row.get("concepts_used") or [])
               for name in concept_names)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    challenges, solutions, experience = load()
    library = ConceptLibrary(OUT / "concept_registry.json")

    # -- stage 1: two independent discoveries become a concept -------------
    discovered = {}
    for tid in SOURCES:
        ast, stats = discover(challenges[tid])
        if ast is not None:
            discovered[tid] = ast
        print(f"source {tid}: discovered={ast is not None} "
              f"hypotheses={stats.hypotheses} classes={stats.semantic_classes}",
              flush=True)
    learned = learn_concepts(discovered, library)
    for concept in learned:
        print(f"LEARNED {concept.name}: class={concept.concept_class} "
              f"slots={concept.free_slots} provenance={concept.provenance}",
              flush=True)
    concepts = [c for c in library.concepts()
                if set(c.provenance) <= set(SOURCES)]
    if not concepts:
        print("no concept learned; nothing to test")
        return

    # -- stage 2: candidates outside the concept's provenance --------------
    candidates = [t for t in experience if t not in SOURCES]
    print(f"\nscanning {len(candidates)} non-provenance Experience tasks "
          f"for ones the concept can express...", flush=True)
    shortlist = []
    for tid in candidates:
        try:
            pairs = [(np.asarray(i), np.asarray(o))
                     for i, o in pairs_of(challenges[tid])]
            if not MI.trigger_fires(pairs):
                continue
            hits, _ = MI.search_with_concepts(pairs, concepts)
            if hits:
                shortlist.append(tid)
        except Exception:
            continue
    print(f"concept expresses {len(shortlist)}: {shortlist}", flush=True)

    # -- stage 3: three conditions at identical budget ---------------------
    names = {c.name for c in concepts}
    witnesses = []
    for tid in shortlist:
        task = challenges[tid]
        without = attempt(task, (), budget_s=30)
        with_c = attempt(task, tuple(concepts), budget_s=30)
        ablated = attempt(task, (), budget_s=30)
        test_correct = test_correct_of(with_c, task, solutions, tid)
        used = uses_concept(with_c, names)
        causal = bool(with_c["accepted"] and used and test_correct is True
                      and not without["accepted"] and not ablated["accepted"])
        efficiency = None
        if with_c["accepted"] and without["accepted"] and used:
            efficiency = {
                "d_hypotheses": without["hypotheses"] - with_c["hypotheses"],
                "d_seconds": round(without["seconds"] - with_c["seconds"], 2),
                "d_size": ((without["size"] or 0) - (with_c["size"] or 0))}
        row = {"task": tid, "without": without, "with_concept": with_c,
               "ablated": ablated, "test_correct": test_correct,
               "uses_concept": used,
               "level_3b_capability": causal,
               "level_3a_efficiency": efficiency}
        witnesses.append(row)
        print(json.dumps({k: v for k, v in row.items()
                          if k not in ("without", "with_concept", "ablated")}),
              flush=True)

    (OUT / "transfer_witnesses.jsonl").write_text(
        "\n".join(json.dumps(w) for w in witnesses))
    causal = [w for w in witnesses if w["level_3b_capability"]]
    efficient = [w for w in witnesses if w["level_3a_efficiency"]
                 and w["level_3a_efficiency"]["d_hypotheses"] > 0]
    print(f"\nLEVEL 3B (capability) witnesses: {len(causal)} / {len(witnesses)}")
    print(f"LEVEL 3A (efficiency) witnesses: {len(efficient)} / {len(witnesses)}")
    if causal:
        # promote only the concepts actually instantiated by a witness
        used_names = set()
        for w in causal:
            if w["with_concept"].get("concept"):
                used_names.add(w["with_concept"]["concept"])
        for concept in concepts:
            if concept.name not in used_names:
                continue
            concept.status = "independent-transfer"
            concept.transfer_witnesses = tuple(
                w["task"] for w in causal
                if w["with_concept"].get("concept") == concept.name)
            library.register(concept)
            print(f"{concept.name} -> independent-transfer "
                  f"({len(concept.transfer_witnesses)} witnesses)")


if __name__ == "__main__":
    main()
