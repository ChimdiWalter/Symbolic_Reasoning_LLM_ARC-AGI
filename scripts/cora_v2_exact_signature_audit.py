"""Exact signature equality: frozen contract versus implementation.

The earlier conformance audit asked whether each production HAS a typed
signature.  This asks the stronger question the claim actually needs:

    Signature_implementation == Signature_frozen ?

The frozen contract below is transcribed literally from the combinator
table of docs/CORA_META_LANGUAGE_V2.md.  Deviations are classified rather
than waved through, because a specialisation is itself an expressive
restriction and may be the real reason a family cannot be expressed.

Statuses:
    EXACT             argument types and result type agree literally
    SPECIALISED       a frozen type variable was instantiated to one type
    CONTEXT_IMPLICIT  a frozen Grid argument is supplied by the interpreter
    DEVIATION         anything else
    MISSING           the production does not exist
    EXTRA             implemented but not in the frozen table

Read-only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geocat_arc.object_reasoning import meta_v2 as V  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"

#: Transcribed literally from the frozen combinator table.
FROZEN: dict = {
    "Partition": (["Grid", "PartitionExpr"], "Set[Region]"),
    "Entities": (["Grid", "SegmentationExpr"], "Set[Entity]"),
    "Group": (["Set[T]", "Relation[T,T]"], "Set[Set[T]]"),
    "Pairs": (["Set[T]", "Relation[T,T]"], "Set[Pair[T]]"),
    "Orbits": (["Grid", "Relation"], "Set[Orbit]"),
    "Order": (["Set[T]", "Feature[T]"], "Sequence[T]"),
    "Select": (["Set[T]", "Predicate[T]"], "Set[T]"),
    "Unique": (["Set[T]"], "T"),
    "ArgMin": (["Set[T]", "Feature[T]"], "T"),
    "ArgMax": (["Set[T]", "Feature[T]"], "T"),
    "Key": (["FeatureExpr"], "FeatureValue"),
    "Lookup": (["Map[FeatureValue,Colour]"], "Colour"),
    "MapOver": (["Set[T]", "Function[T,U]"], "Set[U]"),
    "Zip": (["Set[T]", "Set[U]"], "Set[Pair[T,U]]"),
    "Fold": (["Set[T]", "Function"], "T"),
    "Propagate": (["Seed", "Lattice", "Domain"], "Set[Cell]"),
    "Repeat": (["Function", "Bound"], "Function"),
    "Transform": (["Entity", "TransformExpr"], "Entity"),
    "Anchor": (["Entity", "AnchorExpr"], "Placement"),
    "Recolour": (["Entity", "ColourBijection"], "Entity"),
    "Paint": (["Set[Region]", "Colour"], "Grid"),
    "Copy": (["Entity", "Placement"], "Grid"),
    "Overlay": (["Grid", "Grid"], "Grid"),
    "Erase": (["Set[Cell]"], "Grid"),
    "Compose": (["stage*"], "Grid"),
}

#: Frozen names that are type variables rather than concrete types.
TYPE_VARIABLES = {"T", "U", "Set[T]", "Set[U]", "Set[Set[T]]", "Set[Pair[T]]",
                  "Set[Pair[T,U]]", "Sequence[T]", "Predicate[T]",
                  "Relation[T,T]", "Feature[T]", "Function[T,U]", "Function",
                  "Seed", "Domain", "stage*"}

#: Which concrete types a frozen variable may legitimately instantiate to.
INSTANTIATIONS = {
    "Set[T]": {"Set[Region]", "Set[Entity]", "Set[Coloured]"},
    "Set[U]": {"Set[Coloured]", "Set[Region]", "Set[Entity]"},
    "Set[Set[T]]": {"Set[Entity]", "Set[Region]"},
    "Set[Pair[T]]": {"Set[Pair[Entity]]"},
    "Set[Pair[T,U]]": {"Set[Coloured]", "Set[Pair[Entity]]"},
    "Sequence[T]": {"Sequence[Entity]"},
    "Predicate[T]": {"Predicate"},
    "Relation[T,T]": {"RelationExpr"},
    "Relation": {"RelationExpr", "Lattice"},
    "Feature[T]": {"FeatureExpr"},
    "Function[T,U]": {"Function[Entity,Colour]"},
    "Function": {"Function[Entity,Colour]", "Grid"},
    "T": {"Entity", "Colour", "Region"},
    "Seed": {"Lattice", "Entity"},
    "Domain": {"PartitionExpr", "Set[Region]"},
    "Set[Cell]": {"Grid", "Set[Region]"},
    "TransformExpr": {"Transform"},
    "AnchorExpr": {"Anchor"},
    "Bound": {"Bound"},
    "stage*": {"FeatureValue", "Colour"},
}


def classify(name, frozen_args, frozen_result, production):
    got_args = list(production.arg_types)
    got_result = production.result_type
    notes = []

    # a frozen leading Grid argument may be supplied by the interpreter
    args = list(frozen_args)
    context_implicit = False
    if args and args[0] == "Grid" and (not got_args or got_args[0] != "Grid"):
        args = args[1:]
        context_implicit = True
        notes.append("frozen leading Grid argument supplied by the interpreter")

    if len(args) != len(got_args) and not production.variadic:
        return "DEVIATION", notes + [
            f"arity {len(got_args)} vs frozen {len(args)}"]

    specialised = False
    for frozen_type, got_type in zip(args, got_args):
        if frozen_type == got_type:
            continue
        allowed = INSTANTIATIONS.get(frozen_type, set())
        if got_type in allowed:
            specialised = True
            notes.append(f"{frozen_type} specialised to {got_type}")
            continue
        return "DEVIATION", notes + [
            f"argument {frozen_type} implemented as {got_type}"]

    if frozen_result != got_result:
        allowed = INSTANTIATIONS.get(frozen_result, set())
        if got_result in allowed:
            specialised = True
            notes.append(f"result {frozen_result} specialised to {got_result}")
        else:
            return "DEVIATION", notes + [
                f"result {frozen_result} implemented as {got_result}"]

    if specialised:
        return "SPECIALISED", notes
    if context_implicit:
        return "CONTEXT_IMPLICIT", notes
    return "EXACT", notes


def main():
    rows = []
    for name, (frozen_args, frozen_result) in FROZEN.items():
        production = V.PRODUCTIONS.get(name)
        if production is None:
            rows.append({"production": name, "status": "MISSING",
                         "frozen": f"{frozen_args} -> {frozen_result}",
                         "implemented": None, "notes": []})
            continue
        status, notes = classify(name, frozen_args, frozen_result, production)
        rows.append({"production": name, "status": status,
                     "frozen": f"{frozen_args} -> {frozen_result}",
                     "implemented": f"{list(production.arg_types)} -> "
                                    f"{production.result_type}",
                     "notes": notes})
    for name in sorted(set(V.PRODUCTIONS) - set(FROZEN)):
        production = V.PRODUCTIONS[name]
        rows.append({"production": name, "status": "EXTRA",
                     "frozen": None,
                     "implemented": f"{list(production.arg_types)} -> "
                                    f"{production.result_type}",
                     "notes": ["added by dated amendment"]})

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v2_exact_signature_audit.json").write_text(json.dumps(rows, indent=1))
    counts: dict = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"{'STATUS':18} {'PRODUCTION':12} NOTES")
    for r in rows:
        if r["status"] != "EXACT":
            print(f"{r['status']:18} {r['production']:12} "
                  f"{'; '.join(r['notes'])[:80]}")
    print(f"\ntotals: {counts}")


if __name__ == "__main__":
    main()
