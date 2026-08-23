"""COARSE closure check for the V2.1 semantic contract.

SCOPE, stated plainly: this is a HEAD-TYPE check. It reduces Function[A,B]
to Function, Set[A] to Set and Expr[A=>B] to Expr before asking whether a
constructor exists. So it can show that a contract is obviously broken; it
CANNOT serve as the V2.1 type-soundness proof. The existence of
Function[Region,Colour] does not make Function[Entity,Placement]
constructible, and Set[Region] and Set[Placement] are not interchangeable
downstream. The real checker must unify full parameterised types.

Do not extend this script toward that goal: keep it as the cheap sanity
gate it is.

Is the V2.1 semantic contract internally closed?

One rule, applied to the contract itself rather than to prose:

    no ACTIVE production may depend on a type that no ACTIVE production
    constructs.

That is the general form of ROOT-01. It was found once in the frozen
document and it can reappear inside any contract that marks some rules
inactive, because deactivating a constructor silently strands every rule
that needed it. Checking it mechanically is the only way to be sure the
same defect has not been reintroduced.

Reads outputs/cora_breakthrough/v2_1_semantic_contract.json. Changes
nothing.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (ROOT / "outputs" / "cora_breakthrough"
            / "v2_1_semantic_contract_v2.json")

def terminals_of(contract) -> set:
    """Terminal types, read FROM THE CONTRACT.

    The checker deliberately keeps no list of its own: a hardcoded set here
    is exactly the transcription drift that let the implementation diverge
    from the frozen table in the first place.
    """
    declared = contract.get("terminals", {}).get("types", {})
    if not declared:
        raise SystemExit("contract declares no terminals; refusing to guess")
    return set(declared)


def split_signature(form: str):
    """(argument types, result type) from a 'A x B -> C' string."""
    if "->" not in form:
        return [], None
    left, right = form.rsplit("->", 1)
    args = [a.strip() for a in left.split(" x ") if a.strip()]
    return args, right.strip()


def head(type_text: str) -> str:
    """Outermost type constructor, with parameters stripped."""
    type_text = type_text.strip()
    match = re.match(r"([A-Za-z_]+)", type_text)
    return match.group(1) if match else type_text


def is_variable(type_text: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]", type_text.strip()))


def collect(contract):
    """Every rule with its layer, activity and signature."""
    rules = []
    for judgement in contract["layer_A_evidence_minimal"]["judgements"]:
        rules.append({"layer": "A", **judgement})
    for rule in contract["layer_B_frozen_design"]["rules"]:
        rules.append({"layer": "B", **rule})
    for rule in contract["active_productions"]:
        rules.append({"layer": "P", "active": True, **rule})
    for rule in contract["inactive_unresolved"]:
        rules.append({"layer": "P", "active": False, "form": "", **rule})
    return rules


def main():
    contract = json.loads(CONTRACT.read_text())
    rules = collect(contract)
    terminals = terminals_of(contract)

    constructed_active = set()
    for rule in rules:
        if not rule.get("active", False):
            continue
        _, result = split_signature(rule.get("form", ""))
        if result and not is_variable(result):
            constructed_active.add(head(result))
    constructed_active |= terminals

    findings = []
    for rule in rules:
        if not rule.get("active", False):
            continue
        args, _ = split_signature(rule.get("form", ""))
        for arg in args:
            if is_variable(arg):
                continue
            name = head(arg)
            if name in constructed_active:
                continue
            producers = [other["rule"] for other in rules
                         if split_signature(other.get("form", ""))[1]
                         and head(split_signature(other["form"])[1]) == name]
            inactive_producers = [other["rule"] for other in rules
                                  if other["rule"] in producers
                                  and not other.get("active", False)]
            findings.append({
                "active_rule": rule["rule"], "layer": rule["layer"],
                "needs_type": arg,
                "constructed_by_any_rule": producers or [],
                "but_those_are_inactive": inactive_producers or [],
                "defect": ("ROOT-01 REAPPEARED: an active rule depends on a type "
                           "whose only constructors are inactive"
                           if inactive_producers else
                           "type has no constructor at all in the contract")})

    stranded = []
    for rule in rules:
        if rule.get("active", False):
            continue
        stranded.append(rule["rule"])

    report = {"contract": str(CONTRACT.name),
              "active_constructed_types": sorted(constructed_active),
              "findings": findings,
              "inactive_rules": stranded}
    (CONTRACT.parent / "v2_1_contract_consistency.json").write_text(
        json.dumps(report, indent=1))

    if not findings:
        print("COARSE head-type closure holds: every active rule's argument "
              "types have active constructors")
    else:
        print(f"CONTRACT NOT CLOSED: {len(findings)} defect(s)\n")
        for f in findings:
            print(f"  active rule {f['active_rule']} (layer {f['layer']}) "
                  f"needs {f['needs_type']}")
            print(f"      constructors anywhere: "
                  f"{f['constructed_by_any_rule'] or 'NONE'}")
            print(f"      of those, inactive: "
                  f"{f['but_those_are_inactive'] or 'n/a'}")
            print(f"      {f['defect']}\n")
    print("inactive rules:", ", ".join(stranded))


if __name__ == "__main__":
    main()
