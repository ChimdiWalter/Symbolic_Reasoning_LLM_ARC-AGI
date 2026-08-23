"""Phase 3: relearn the concept natively, with four certificates.

Still the same two source tasks, so this is V2.1-native Level-2
REPRODUCTION, not prospective evidence. New transfer evidence begins at
Phase 5, when the frozen concept meets tasks outside its provenance.
"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning import meta_v21 as V  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_concept as C  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_search as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"
REGISTRY_PATH = OUT / "v21_concept_registry.json"
SOURCES = ("7b6016b9", "83302e8f")


def agreements_kept(first, second, schema) -> bool:
    """Every position where the two programs agreed is still concrete."""

    def walk(a, b, s):
        if V.is_ast(a) and V.is_ast(b) and a[0] == b[0]:
            if not V.is_ast(s) or s[0] != a[0]:
                return False
            return all(walk(x, y, z) for x, y, z in zip(a[1], b[1], s[1]))
        if repr(a) == repr(b):
            return repr(s) == repr(a)
        return isinstance(s, str) and s.startswith("?v")

    return walk(first, second, schema)


def main():
    if REGISTRY_PATH.exists():
        REGISTRY_PATH.unlink()             # fresh registry, never seeded
    challenges = json.loads(
        (ROOT / "data" / "arc-agi_training_challenges.json").read_text())

    discovered = {}
    for task_id in SOURCES:
        pairs = [(np.array(p["input"]), np.array(p["output"]))
                 for p in challenges[task_id]["train"]]
        results, _ = S.search(pairs)
        if not results:
            print(f"{task_id}: no program discovered; cannot proceed")
            return
        discovered[task_id] = results[0][0]
        print(f"{task_id}: discovered, hash {C.program_hash(results[0][0])}",
              flush=True)

    registry = C.ConceptRegistry(REGISTRY_PATH)
    concept = C.learn_concept(discovered, registry.next_name())
    if concept is None:
        print("anti-unification produced no concept")
        return
    slots = C.introduced_slots(concept.schema)
    print(f"\nLEARNED {concept.name}")
    print("  schema:", json.dumps(V.to_json(concept.schema))[:240])
    print("  slots:", {s: str(concept.slot_types[s]) for s in slots})
    print("  provenance:", concept.provenance)

    forward = C.anti_unify(discovered[SOURCES[0]], discovered[SOURCES[1]])
    backward = C.anti_unify(discovered[SOURCES[1]], discovered[SOURCES[0]])
    symmetric = C.rename_slots(forward.schema) == C.rename_slots(backward.schema)

    reconstructions = {}
    for index, task_id in enumerate(sorted(discovered)):
        binding = {s: forward.bindings[index][s] for s in slots}
        reconstructions[task_id] = (
            C.instantiate(concept.schema, binding) == discovered[task_id])

    genuine = all(repr(forward.bindings[0][s]) != repr(forward.bindings[1][s])
                  for s in slots)
    kept = agreements_kept(discovered[SOURCES[0]], discovered[SOURCES[1]],
                           concept.schema)

    # certificate 5: every recorded source binding typechecks against its
    # slot's declared type
    def binding_ok(value, declared) -> bool:
        key = str(declared)
        if key in V.TERMINAL_VALUES:
            return value in V.TERMINAL_VALUES[key]
        if key in V.INDUCED_TYPES:
            return isinstance(value, tuple)     # a fitted table or value
        got = V.type_of(value) if V.is_ast(value) else None
        return got is not None and V.type_equal(got, declared)

    binding_types = {}
    for index, task_id in enumerate(sorted(discovered)):
        binding_types[task_id] = {
            slot: binding_ok(forward.bindings[index][slot],
                             concept.slot_types[slot]) for slot in slots}
    bindings_typecheck = all(all(v.values()) for v in binding_types.values())

    au_source = inspect.getsource(C)
    fresh = {"registry_was_empty_at_start": True,
             "old_registry_not_loaded": "concept_registry.json" not in au_source,
             "no_task_ids_in_anti_unifier": not any(t in au_source
                                                    for t in SOURCES),
             "no_concept_names_in_logic": "concept_0001" not in au_source,
             "source_program_sha256": list(concept.source_hashes)}

    certificates = {"symmetry_up_to_renaming": symmetric,
                    "source_bindings_typecheck": binding_types,
                    "exact_reconstruction": reconstructions,
                    "least_generality": {
                        "every_slot_is_a_real_disagreement": genuine,
                        "agreements_retained": kept},
                    "freshness": fresh}
    all_green = (symmetric and all(reconstructions.values()) and genuine
                 and bindings_typecheck
                 and kept and fresh["old_registry_not_loaded"]
                 and fresh["no_task_ids_in_anti_unifier"]
                 and fresh["no_concept_names_in_logic"])

    print("\nCERTIFICATES")
    print(json.dumps(certificates, indent=1, default=str))
    print(f"\nall green: {all_green}")
    if all_green:
        registry.register(concept)
        print(f"{concept.name} persisted to {REGISTRY_PATH.name}")
    (OUT / "v21_phase3_certificates.json").write_text(json.dumps(
        {"concept": concept.to_dict(), "certificates": certificates,
         "all_green": all_green,
         "status": ("V2.1-native reproduction of Level-2 abstraction "
                    "invention; NOT prospective transfer evidence")},
        indent=1, default=str))


if __name__ == "__main__":
    main()
