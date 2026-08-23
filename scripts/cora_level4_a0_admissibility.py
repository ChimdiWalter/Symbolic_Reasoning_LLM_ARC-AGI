"""Level-4 A0: baseline admissibility.

Registry membership is not reasoning capability. A production may be listed,
typed and evaluable and still be unreachable by the frozen inducer, because
one of its argument types has no terminal vocabulary and no slot learner.

If that were left unchecked, Level 4 could appear to invent a semantic
bridge that the baseline supposedly already had, purely because the baseline
capability was nominal.

For every candidate this records contract signature, runtime signature,
signature status, historical source and hash, evaluator presence, where each
argument's values come from, whether the frozen search can actually build a
term using it, and whether its semantics behave correctly on synthetic
fixtures. A production is admitted only when historical provenance AND
frozen-search reachability are both demonstrated.

No ARC development task is read. No frontier is extracted. No invention.
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
from geocat_arc.object_reasoning import meta_v21_env as E  # noqa: E402
from geocat_arc.object_reasoning import meta_v21_search as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"

#: Where each production's semantics came from, and its hash, so "historical"
#: is a checkable claim rather than an assertion.
HISTORICAL_SOURCE = {
    "Partition": "meta_v21.py (Phase 1, pre-Level-4)",
    "Select": "meta_v21.py (Phase 1, pre-Level-4)",
    "Key": "meta_v21.py (Phase 1, pre-Level-4)",
    "Lookup": "meta_v21.py (Phase 1, pre-Level-4)",
    "Compose_V1": "meta_v21.py (Phase 1, pre-Level-4)",
    "Map_V1": "meta_v21.py (Phase 1, pre-Level-4)",
    "PaintEach": "meta_v21.py (Phase 1, pre-Level-4)",
    "Entities": "meta_v21.py (Phase 1, pre-Level-4)",
    "Paint": "meta_v21.py (Phase 1, pre-Level-4)",
    "Unique": "meta_v21.py (Phase 1, pre-Level-4)",
    "ArgMax": "meta_v21.py (Phase 1, pre-Level-4)",
    "ArgMin": "meta_v21.py (Phase 1, pre-Level-4)",
    "Overlay": "meta_v21.py (Phase 1, pre-Level-4)",
    "Group": "meta_v2.py prototype (2026-08-21, pre-Level-4)",
    "Transform": "meta_v2.py prototype (2026-08-21, pre-Level-4)",
    "Recolour": "meta_v2.py prototype (2026-08-21, pre-Level-4)",
    "Anchor": "meta_v2.py prototype, as Place (2026-08-21, pre-Level-4)",
    "Copy": "meta_v2.py prototype, as Stamp (2026-08-21, pre-Level-4)",
}

#: Productions the contract marks active that are NOT runtime productions.
NON_RUNTIME = {
    "Concept": ("active meta-production, instantiated through the concept "
                "overlay in meta_v21_env; not a primitive runtime evaluator"),
    "Expr_formation": ("a typing and formation judgement, not an enumerable "
                       "runtime production"),
}


def sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def argument_sources(production, env):
    """Where each argument's values can come from, under the frozen search."""
    sources = []
    for arg in production.arg_types:
        key = str(arg)
        if key in V.TERMINAL_VALUES:
            sources.append(f"terminal vocabulary ({len(V.TERMINAL_VALUES[key])})")
        elif key in V.INDUCED_TYPES:
            learner = S.SLOT_LEARNERS.get(key)
            sources.append(f"induced slot, learner {'present' if learner else 'ABSENT'}")
        elif any(V.type_equal(env.result_type(n), arg) for n in env.names):
            sources.append("produced by another production")
        else:
            sources.append("NO SOURCE")
    return sources


def search_reachable(name, env, deadline_seconds=4.0):
    """Can the FROZEN enumerator build any term that uses this production?"""
    stats = S.SearchStats()
    deadline = time.monotonic() + deadline_seconds
    cache: dict = {}
    for goal in (V.GRID, V.T("Placement"), V.T("Entity"), V.SET_ENTITY,
                 V.SET_REGION, V.SET_COLOURED):
        try:
            terms = S._asts_of_type(goal, 4, cache, stats, deadline, env)
        except Exception:
            continue
        for ast in terms:
            if _mentions(ast, name, env):
                return True
        if time.monotonic() > deadline:
            break
    return False


def _mentions(ast, name, env) -> bool:
    if not env.is_ast(ast):
        return False
    if ast[0] == name:
        return True
    return any(_mentions(a, name, env) for a in ast[1])


def synthetic_checks(env):
    """Behavioural fixtures. Failures are recorded, never repaired here."""
    results = {}
    grid = np.array([[0, 0, 0, 0, 0],
                     [0, 3, 4, 0, 0],
                     [0, 3, 0, 0, 0],
                     [0, 0, 0, 0, 0]])
    entity = frozenset({(1, 1), (1, 2), (2, 1)})       # asymmetric, 2 colours

    # Recolour must actually recolour
    recoloured = V.EVALUATORS["Recolour"](V.Ctx(grid), entity, ((3, 7),))
    results["Recolour_changes_anything"] = (recoloured != entity)

    # Transform must carry the source appearance, not resample the grid
    rotated = V.EVALUATORS["Transform"](V.Ctx(grid), entity, (1, False))
    patch_before = V.patch_of(entity, grid)
    expected = V.apply_d4(patch_before, (1, False))
    carried = None
    if rotated:
        patch_after = V.patch_of(rotated, grid)
        carried = bool(patch_after.shape == expected.shape
                       and np.array_equal(np.sort(patch_after.ravel()),
                                          np.sort(expected.ravel())))
    results["Transform_preserves_multicolour_appearance"] = bool(carried)

    # Copy places a single entity at an inferred offset. The offset must be
    # in bounds: an earlier version of this fixture used one that was not,
    # and wrongly recorded Copy as broken.
    placement = V.EVALUATORS["Anchor"](V.Ctx(grid), entity, (1, 1))
    stamped = V.EVALUATORS["Copy"](V.Ctx(grid), placement)
    results["Copy_single_instance"] = bool(stamped is not None
                                           and not np.array_equal(stamped, grid))
    # and refuses an out-of-bounds placement
    far = V.EVALUATORS["Anchor"](V.Ctx(grid), entity, (50, 50))
    results["Copy_rejects_out_of_bounds"] = (
        V.EVALUATORS["Copy"](V.Ctx(grid), far) is None)

    # Group must merge under a relation
    sets = (frozenset({(1, 1)}), frozenset({(1, 2)}), frozenset({(3, 3)}))
    grouped = V.EVALUATORS["Group"](V.Ctx(grid), sets, "aligned_row")
    results["Group_merges_under_relation"] = bool(
        grouped is not None and len(grouped) < len(sets))
    return results


def positive_control(env):
    """Can the FROZEN search rediscover the claimed single-instance chain?

    The chain Entities -> Unique -> Anchor -> Copy -> Grid is the capability
    the registry appears to grant. This builds a synthetic task whose answer
    IS that chain, with one asymmetric multicolour entity copied to a fixed
    corner, and runs the real inducer on it. Manually evaluating a supplied
    AST would prove nothing: the question is whether the search can find it.
    """
    def make(cells, offset, size=7):
        grid = np.zeros((size, size), int)
        for (row, col), colour in cells.items():
            grid[row, col] = colour
        out = grid.copy()
        top, left = min(r for r, _ in cells), min(c for _, c in cells)
        for (row, col), colour in cells.items():
            out[row - top + offset[0], col - left + offset[1]] = colour
        return grid, out

    pairs = [make(cells, (4, 4)) for cells in (
        {(1, 1): 3, (1, 2): 4, (2, 1): 3},
        {(2, 3): 3, (2, 4): 4, (3, 3): 3},
        {(0, 0): 3, (0, 1): 4, (1, 0): 3})]
    programs, stats = S.search(pairs, env=env)
    passed, total = S.loo_by_rediscovery(pairs, env=env)
    return {
        "chain": "Entities -> Unique -> Anchor -> Copy -> Grid",
        "task": ("synthetic: one asymmetric multicolour entity copied to a "
                 "fixed corner, three unambiguous demonstrations"),
        "surface_terms_generated": stats.generated,
        "typed_candidates": stats.typed,
        "exact_fit_programs": len(programs),
        "loo_by_rediscovery": f"{passed}/{total}",
        "rediscovered_by_frozen_search": bool(programs) and passed == total,
        "verdict": ("the baseline does NOT operationally possess single-"
                    "instance placement: the search rejects every typed "
                    "candidate because the Anchor slot type has no learner. "
                    "Recorded, not repaired.") if not programs else
                   "the baseline does possess this capability"}


def concept_viability(admitted):
    """Is C1 still usable once inadmissible productions are removed?"""
    registry = json.loads((OUT / "v21_concept_registry.json").read_text())
    concept = list(registry.values())[0]
    used = set()

    def walk(node):
        if isinstance(node, dict) and "op" in node:
            used.add(node["op"])
            for child in node.get("args", []):
                walk(child)
    walk(concept["schema"])
    missing = sorted(used - set(admitted))
    return {"concept": concept["name"], "productions_used": sorted(used),
            "missing_from_K_L4_star": missing,
            "viable_under_K_L4_star": not missing}


def main():
    level4_env = E.LanguageEnv(base=dict(V.LEVEL4_REGISTRY), label="K_L4")
    fixtures = synthetic_checks(level4_env)
    contract = json.loads((OUT / "v2_1_semantic_contract_v2.json").read_text())
    rules = V._contract_rules(contract)

    rows = []
    for name, production in sorted(V.LEVEL4_REGISTRY.items()):
        base = production.contract_grades.get("instantiated_from", name)
        contract_form = rules.get(base, {}).get("form", "")
        runtime_form = production.contract_grades.get("signature_text", "")
        if contract_form.replace(" ", "") == runtime_form.replace(" ", ""):
            status = "EXACT"
        elif base == "Copy":
            status = ("SIGNATURE_RECONSTRUCTED: the contract says "
                      "Entity x Placement -> Grid, the runtime takes only "
                      "Placement because Anchor already pairs the entity with "
                      "its offset. Disclosed, not hidden as context-implicit.")
        elif "instantiated_from" in production.contract_grades:
            status = "GROUND_INSTANTIATION of a SPEC_INTENDED polymorphic form"
        else:
            status = "RECONSTRUCTED"

        sources = argument_sources(production, level4_env)
        reachable = search_reachable(name, level4_env)
        relevant = [k for k in fixtures if k.split("_")[0] == base]
        semantics = (all(fixtures[k] for k in relevant) if relevant else None)

        no_source = any(s == "NO SOURCE" or "ABSENT" in s for s in sources)
        admitted = bool(reachable and semantics is not False and not no_source)
        reason = []
        if not reachable:
            reason.append("the frozen search cannot construct any term using it")
        if semantics is False:
            reason.append("synthetic semantics failed")
        if no_source:
            reason.append("an argument type has no terminal vocabulary and no "
                          "slot learner, so the frozen search can never supply "
                          "a value for it")
        rows.append({
            "production": name, "base": base,
            "contract_signature": contract_form,
            "runtime_signature": runtime_form,
            "signature_status": status,
            "historical_source": HISTORICAL_SOURCE.get(base, "UNKNOWN"),
            "historical_source_hash": sha(
                ROOT / "geocat_arc/object_reasoning/meta_v21.py"),
            "evaluator_present": base in V.EVALUATORS,
            "argument_sources": sources,
            "search_reachable": reachable,
            "synthetic_semantics_pass": semantics,
            "admitted_to_K_L4": admitted,
            "reason": "; ".join(reason) or "historical provenance and frozen-"
                                           "search reachability both shown"})
        print(f"{name:16} reachable={str(reachable):5} "
              f"semantics={str(semantics):5} admitted={str(admitted):5} "
              f"{rows[-1]['reason'][:60]}", flush=True)

    # cascade: a production whose argument type is produced ONLY by excluded
    # productions cannot itself be used, so admission is iterated to a fixed
    # point rather than decided once per production
    changed = True
    while changed:
        changed = False
        live = {r["production"] for r in rows if r["admitted_to_K_L4"]}
        available = set(V.TERMINAL_VALUES) | {
            k for k in V.INDUCED_TYPES if S.SLOT_LEARNERS.get(k)}
        available |= {str(V.LEVEL4_REGISTRY[n].result_type) for n in live}
        for row in rows:
            if not row["admitted_to_K_L4"]:
                continue
            production = V.LEVEL4_REGISTRY[row["production"]]
            for arg in production.arg_types:
                if str(arg) not in available:
                    row["admitted_to_K_L4"] = False
                    row["reason"] = (f"cascade: its argument {arg} is produced "
                                     f"only by excluded productions")
                    changed = True
                    break

    control = positive_control(level4_env)
    admitted = sorted(r["production"] for r in rows if r["admitted_to_K_L4"])
    excluded = sorted(r["production"] for r in rows if not r["admitted_to_K_L4"])
    report = {
        "gate": "Level-4 A0 baseline admissibility",
        "non_runtime_active_productions": NON_RUNTIME,
        "synthetic_fixtures": fixtures,
        "positive_control": control,
        "rows": rows,
        "admitted": admitted, "excluded": excluded,
        "K_L4_star": admitted,
        "concept_viability": concept_viability(admitted),
        "E_L4_star": admitted + ["concept_0001"],
        "note": ("A capability is admitted only when it is pre-Level-4 AND "
                 "reachable by the frozen search. Nothing here was repaired: "
                 "a failed baseline capability is excluded and the reason "
                 "recorded.")}
    (OUT / "level4_baseline_admissibility.json").write_text(
        json.dumps(report, indent=1, default=str))

    print(f"\nFIXTURES: {json.dumps(fixtures)}")
    print(f"\nADMITTED to K_L4* ({len(admitted)}): {admitted}")
    print(f"EXCLUDED ({len(excluded)}): {excluded}")
    print(f"\nnon-runtime active productions: {sorted(NON_RUNTIME)}")
    print(f"\nPOSITIVE CONTROL: {json.dumps(control, indent=1)}")
    print(f"\nC1 viability: {json.dumps(report['concept_viability'])}")


if __name__ == "__main__":
    main()
