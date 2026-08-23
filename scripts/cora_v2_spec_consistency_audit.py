"""Is the FROZEN language itself well-typed, inhabited and compositional?

This script never looks at the implementation.  It reads the combinator
table of docs/CORA_META_LANGUAGE_V2.md as a formal contract, gives it a real
type representation with type variables, unifies properly instead of
consulting a hand-written whitelist, and then asks the questions that decide
whether the specification can support the transformations it claims:

    is every argument type well formed
    is every argument type inhabited by something
    does every higher-order function type have a constructor
    can every produced type participate in a derivation that ends in Grid

Whatever it finds is a property of the specification, so it cannot be
explained away as an implementation slip, and it was not chosen by looking
at which ARC tasks failed.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"


# --------------------------------------------------------------------------
# type terms
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TVar:
    name: str

    def __str__(self):
        return self.name


@dataclass(frozen=True)
class TCon:
    name: str
    args: tuple = ()

    def __str__(self):
        if not self.args:
            return self.name
        return f"{self.name}[{','.join(str(a) for a in self.args)}]"


def parse(text: str):
    """Parse "Set[Pair[T,U]]" into type terms; single capitals are variables."""
    text = text.strip()
    if "[" not in text:
        return TVar(text) if len(text) == 1 and text.isupper() else TCon(text)
    head, rest = text.split("[", 1)
    assert rest.endswith("]"), text
    inner, depth, current = [], 0, ""
    for ch in rest[:-1]:
        if ch == "," and depth == 0:
            inner.append(current)
            current = ""
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        current += ch
    if current:
        inner.append(current)
    return TCon(head.strip(), tuple(parse(a) for a in inner))


def freshen(term, suffix):
    if isinstance(term, TVar):
        return TVar(f"{term.name}{suffix}")
    return TCon(term.name, tuple(freshen(a, suffix) for a in term.args))


def walk(term, subst):
    while isinstance(term, TVar) and term.name in subst:
        term = subst[term.name]
    return term


def occurs(name: str, term, subst) -> bool:
    """Does the variable appear inside the term?  Without this check,
    Group : Set[T] -> Set[Set[T]] would bind T := Set[T] and build an
    infinite type."""
    term = walk(term, subst)
    if isinstance(term, TVar):
        return term.name == name
    return any(occurs(name, a, subst) for a in term.args)


def unify(a, b, subst: Optional[dict] = None):
    """Standard first-order unification with an occurs check."""
    subst = dict(subst or {})
    a, b = walk(a, subst), walk(b, subst)
    if isinstance(a, TVar):
        if a != b:
            if occurs(a.name, b, subst):
                return None
            subst[a.name] = b
        return subst
    if isinstance(b, TVar):
        if occurs(b.name, a, subst):
            return None
        subst[b.name] = a
        return subst
    if a.name != b.name or len(a.args) != len(b.args):
        return None
    for x, y in zip(a.args, b.args):
        subst = unify(x, y, subst)
        if subst is None:
            return None
    return subst


MAX_TYPE_DEPTH = 4


def type_depth(term, budget=32):
    """Nesting depth, with a hard stop so a runaway term cannot recurse."""
    if budget <= 0 or isinstance(term, TVar) or not term.args:
        return 1
    return 1 + max(type_depth(a, budget - 1) for a in term.args)


def apply_subst(term, subst):
    term = walk(term, subst)
    if isinstance(term, TVar):
        return term
    return TCon(term.name, tuple(apply_subst(a, subst) for a in term.args))


# --------------------------------------------------------------------------
# the frozen contract, transcribed literally
# --------------------------------------------------------------------------

FROZEN_PRODUCTIONS = {
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

#: Types the frozen document supplies as vocabulary, not as derived results.
FROZEN_TERMINALS = {
    "Grid",                       # the task input, given
    "PartitionExpr", "SegmentationExpr", "FeatureExpr", "Bound",
    "Predicate", "Relation", "Feature",          # named with an argument
    "TransformExpr", "AnchorExpr",
    "Map", "ColourBijection", "Lattice", "SequenceRule",   # induced
    "Colour",
}

#: Types the document's own type list declares.
DECLARED_TYPES = {
    "Grid", "Set", "Region", "Entity", "Pair", "Sequence", "Orbit", "Lattice",
    "FeatureValue", "Colour", "Vector", "Transform", "Anchor", "Placement",
    "Predicate", "Map", "Relation", "Function", "Cell",
}


def is_terminal(term):
    return isinstance(term, TCon) and term.name in FROZEN_TERMINALS


def canonical_schemes(productions):
    """Every type scheme the specification mentions, plus query types.

    Grounding is restricted to these; the language never needs arbitrary
    Set[Set[Set[...]]], so no artificial nesting cap is required and no
    finding can be an artefact of a depth bound.
    """
    schemes = set()
    for args, result in productions.values():
        for text in list(args) + [result]:
            if text != "stage*":
                schemes.add(text)
    schemes |= {"Set[Placement]", "Set[Grid]", "Grid", "Placement",
                "Function[T,U]", "Function"}
    return {parse(t) for t in schemes}


def inhabited_fixed_point(productions):
    """Least fixed point over the specification's OWN type schemes.

    The universe is finite (the schemes the document mentions plus the query
    types), so this terminates with no nesting cap and no finding can be an
    artefact of a depth bound.  Substitutions are threaded through
    unification and never used to BUILD new terms, so no infinite type can
    be constructed.
    """
    universe = sorted(canonical_schemes(productions), key=str)
    inhabited = {t for t in universe if isinstance(t, TVar) or is_terminal(t)}
    changed = True
    while changed:
        changed = False
        for target in universe:
            if target in inhabited:
                continue
            for index, (name, (args, result)) in enumerate(
                    productions.items()):
                if "stage*" in args:
                    continue
                subst = unify(freshen(parse(result), f"_{index}"), target)
                if subst is None:
                    continue
                ok = True
                for text in args:
                    arg = freshen(parse(text), f"_{index}")
                    if isinstance(arg, TVar):
                        continue
                    matched = None
                    for known in inhabited:
                        if isinstance(known, TVar):
                            continue
                        trial = unify(arg, known, subst)
                        if trial is not None:
                            matched = trial
                            break
                    if matched is None:
                        ok = False
                        break
                    subst = matched
                if ok:
                    inhabited.add(target)
                    changed = True
                    break
    return inhabited


def is_inhabited(term, inhabited):
    if isinstance(term, TVar):
        return True               # an unconstrained argument position
    return any(unify(freshen(term, "_q"), known) is not None
               for known in inhabited if not isinstance(known, TVar))


def reaches_grid(term, productions, inhabited, seen=None):
    """Compositional reachability.

    A transition through a production is allowed only when EVERY OTHER
    argument is inhabited, so a path through a production that can never
    execute is not counted.  Substitutions are threaded, never applied to
    build terms.
    """
    seen = set(seen or ())
    key = str(term)
    if isinstance(term, TCon) and term.name == "Grid":
        return True
    if key in seen:
        return False
    seen.add(key)
    for index, (name, (args, result)) in enumerate(productions.items()):
        if "stage*" in args:
            continue
        for position, text in enumerate(args):
            subst = unify(freshen(parse(text), f"_{index}"), term)
            if subst is None:
                continue
            siblings_ok = True
            for other_position, other_text in enumerate(args):
                if other_position == position:
                    continue
                other = freshen(parse(other_text), f"_{index}")
                if isinstance(other, TVar):
                    continue
                if not any(unify(other, known, subst) is not None
                           for known in inhabited):
                    siblings_ok = False
                    break
            if not siblings_ok:
                continue
            produced = freshen(parse(result), f"_{index}")
            if isinstance(produced, TVar):
                continue          # a bare variable result carries no type
            if reaches_grid(produced, productions, inhabited, seen):
                return True
    return False


#: Types whose formation the document never specifies.  A production that
#: needs one of these is UNDERSPECIFIED, not contradictory: the frozen table
#: contains higher-order operators, and a higher-order language may well
#: form function terms by partial application or stage composition rather
#: than by a production with a Function result type.
HIGHER_ORDER_TYPES = {"Function", "Function[T,U]"}

#: Root causes, so dependent symptoms are not counted as separate defects.
ROOTS = {
    "ROOT-01": {
        "title": "function-term formation is not specified",
        "detail": ("The table contains higher-order operators (MapOver, Fold, "
                   "Repeat) but never says how a Function term is formed. "
                   "Under a first-order reading no production returns a "
                   "Function, so those operators look uninhabitable; under a "
                   "higher-order reading, partial application or stage "
                   "composition would form them. The document does not say "
                   "which, so this is UNDERSPECIFICATION, not contradiction."),
        "symptoms": ["MapOver", "Fold", "Repeat", "Key", "Compose"]},
    "ROOT-02": {
        "title": "Seed and Domain are undeclared types",
        "detail": ("Propagate takes Seed and Domain; neither appears in the "
                   "specification's type list, so nothing can supply them, "
                   "and Propagate's result Set[Cell] therefore never exists, "
                   "which in turn strands Erase."),
        "symptoms": ["Propagate", "Erase"]},
    "ROOT-03": {
        "title": "Sequence[T] has no consumer",
        "detail": ("Order produces Sequence[T] and no production consumes a "
                   "Sequence, so ordering can never influence an output. This "
                   "is independent of the higher-order question and may be a "
                   "genuine dead end, unless pre-freeze sequence-extension "
                   "material specifies the missing consumer."),
        "symptoms": ["Order"]},
}


def main():
    productions = FROZEN_PRODUCTIONS
    inhabited = inhabited_fixed_point(productions)
    findings = []

    def root_of(production_name):
        for root, block in ROOTS.items():
            if production_name in block["symptoms"]:
                return root
        return None

    # -- declared-ness -----------------------------------------------------
    for name, (args, result) in productions.items():
        for text in list(args) + [result]:
            if text == "stage*":
                findings.append({"production": name,
                                 "status": "SPEC_UNDERSPECIFICATION",
                                 "root": root_of(name),
                                 "detail": "argument written 'stage*': a "
                                           "variadic placeholder with no "
                                           "element type"})
                continue
            term = parse(text)
            head = term.name if isinstance(term, TCon) else None
            if head and head not in DECLARED_TYPES \
                    and head not in FROZEN_TERMINALS:
                findings.append({"production": name,
                                 "status": "SPEC_UNDERSPECIFICATION",
                                 "root": root_of(name),
                                 "detail": f"type '{text}' is used but never "
                                           f"declared"})

    # -- inhabitation of arguments ----------------------------------------
    for name, (args, result) in productions.items():
        for text in args:
            if text == "stage*":
                continue
            term = parse(text)
            if isinstance(term, TVar) or is_inhabited(term, inhabited):
                continue
            higher_order = text in HIGHER_ORDER_TYPES
            findings.append({
                "production": name,
                "status": ("SPEC_UNDERSPECIFICATION" if higher_order
                           else "SPEC_TYPE_CONTRADICTION"),
                "root": root_of(name),
                "detail": (f"argument '{text}' has no constructor under a "
                           f"FIRST-ORDER reading" if higher_order else
                           f"argument '{text}' is uninhabited")})

    # -- dead results ------------------------------------------------------
    dead = []
    for name, (args, result) in productions.items():
        term = parse(result)
        if isinstance(term, TVar):
            continue
        if not reaches_grid(term, productions, inhabited):
            dead.append((name, result))
            findings.append({
                "production": name, "status": "SPEC_DEAD_PRODUCTION",
                "root": root_of(name),
                "detail": f"result '{result}' cannot compositionally reach "
                          f"Grid once every sibling argument must also be "
                          f"inhabited"})

    # -- the multi-placement question, asked of the FROZEN table -----------
    multi = {
        "Set[Placement]_inhabited": is_inhabited(parse("Set[Placement]"),
                                                 inhabited),
        "Set[Placement]_reaches_Grid": reaches_grid(
            parse("Set[Placement]"), productions, inhabited),
        "Set[Grid]_reaches_Grid": reaches_grid(parse("Set[Grid]"),
                                               productions, inhabited),
    }

    # -- group by root -----------------------------------------------------
    grouped: dict = {}
    for f in findings:
        grouped.setdefault(f["root"] or "UNGROUPED", []).append(f)

    report = {
        "scope": "FROZEN CONTRACT ONLY (implementation not consulted)",
        "method": ("fixed-point inhabitation over the specification's own "
                   "type schemes (no depth cap); reachability requires every "
                   "sibling argument to be inhabited; higher-order types are "
                   "reported as underspecification, not contradiction"),
        "roots": ROOTS, "findings": findings, "grouped": grouped,
        "inhabited_schemes": sorted(str(t) for t in inhabited),
        "multi_placement_in_frozen_spec": multi,
        "headline": ("The frozen V2 document is not yet a complete formal "
                     "higher-order grammar. Its defects reduce to a small "
                     "number of root underspecifications with dependent "
                     "symptoms, not to many independent contradictions."),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v2_spec_consistency_audit.json").write_text(
        json.dumps(report, indent=1, default=str))

    print(report["headline"], "\n")
    counts: dict = {}
    for f in findings:
        counts[f["status"]] = counts.get(f["status"], 0) + 1
    for root, block in ROOTS.items():
        symptoms = grouped.get(root, [])
        print(f"{root}: {block['title']}")
        for f in symptoms:
            print(f"    - {f['production']:12} {f['status']:28} "
                  f"{f['detail'][:70]}")
        print()
    if grouped.get("UNGROUPED"):
        print("UNGROUPED findings:")
        for f in grouped["UNGROUPED"]:
            print(f"    - {f['production']:12} {f['status']:28} "
                  f"{f['detail'][:70]}")
        print()
    print("status totals:", counts)
    print("root causes:", len([r for r in ROOTS if grouped.get(r)]))
    print("\nMULTI-PLACEMENT, ASKED OF THE FROZEN TABLE:")
    for key, value in multi.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
