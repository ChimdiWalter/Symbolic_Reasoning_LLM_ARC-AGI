"""Evidence discipline in the V2.1 semantic contract.

The closure check asks whether the contract is buildable. This asks the
different and more important question: whether it is honest.

Six rules, each aimed at a way a later choice can quietly acquire the
authority of a historical observation:

    1. no COMPATIBLE-only rule may be implementation_required
    2. no UNRESOLVED rule may be active
    3. every DESIGN_RESOLUTION carries an explicit rationale
    4. every OBSERVED behaviour cites evidence
    5. every polymorphic signature carries its own polymorphism grade
    6. no rule upgrades design intent to observation

Rule 6 is the one that matters most: a signature that was never executed
must not be graded OBSERVED merely because some related behaviour was.

Reads outputs/cora_breakthrough/v2_1_semantic_contract_v2.json. Changes
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

EVIDENCE_GRADES = {"OBSERVED", "LOGICALLY_REQUIRED", "SPEC_INTENDED",
                   "COMPATIBLE", "DESIGN_RESOLUTION", "UNRESOLVED",
                   "MONOMORPHIC_NO_VARIABLES"}

#: How much authority each grade carries. A rule may not claim more
#: authority in a derived field than its behaviour evidence supports.
AUTHORITY = {"OBSERVED": 4, "LOGICALLY_REQUIRED": 3, "SPEC_INTENDED": 2,
             "DESIGN_RESOLUTION": 2, "COMPATIBLE": 1, "UNRESOLVED": 0,
             "MONOMORPHIC_NO_VARIABLES": 0}


def collect(contract):
    rules = []
    for r in contract["layer_A_evidence_minimal"]["judgements"]:
        rules.append({"section": "layer_A", **r})
    for r in contract["layer_B_frozen_design"]["rules"]:
        rules.append({"section": "layer_B", **r})
    for r in contract["active_productions"]:
        rules.append({"section": "active", **r})
    for r in contract["inactive_unresolved"]:
        rules.append({"section": "inactive", **r})
    return rules


def has_type_variables(form: str) -> bool:
    """Does the signature quantify over a type variable?"""
    if not form:
        return False
    stripped = re.sub(r"[A-Za-z_]{2,}", " ", form)      # drop long names
    return bool(re.search(r"\b[A-Z]\b", stripped))


def main():
    contract = json.loads(CONTRACT.read_text())
    rules = collect(contract)
    resolutions = contract.get("design_resolutions", {})
    violations = []

    for rule in rules:
        name = rule["rule"]
        behaviour = rule.get("behavior_grade")
        signature = rule.get("signature_grade")
        polymorphism = rule.get("polymorphism_grade")
        active = rule.get("active", False)
        evidence = rule.get("evidence") or []

        for field, grade in (("behavior_grade", behaviour),
                             ("signature_grade", signature),
                             ("polymorphism_grade", polymorphism)):
            if grade is None:
                violations.append((name, f"missing {field}"))
            elif grade not in EVIDENCE_GRADES:
                violations.append((name, f"{field} has unknown grade {grade}"))

        # 1. COMPATIBLE-only rules may not be required of an implementation
        grades = {behaviour, signature, polymorphism} - {None}
        if grades and grades <= {"COMPATIBLE", "MONOMORPHIC_NO_VARIABLES"} \
                and rule.get("implementation_required"):
            violations.append((name, "COMPATIBLE-only rule is implementation_required"))

        # 2. UNRESOLVED rules may not be active
        if active and "UNRESOLVED" in grades:
            violations.append((name, "UNRESOLVED rule is active"))

        # 3. every DESIGN_RESOLUTION carries a rationale
        if "DESIGN_RESOLUTION" in grades:
            identifier = rule.get("design_resolution_id")
            if not identifier:
                violations.append((name, "DESIGN_RESOLUTION without a design_resolution_id"))
            elif identifier not in resolutions:
                violations.append((name, f"design_resolution_id {identifier} is not defined"))
            elif not resolutions[identifier].get("rationale"):
                violations.append((name, f"{identifier} has no rationale"))

        # 4. every OBSERVED behaviour cites evidence
        if behaviour == "OBSERVED" and not evidence:
            violations.append((name, "behaviour graded OBSERVED with no evidence cited"))

        # 5. a polymorphic signature needs its own grade, not a placeholder
        if has_type_variables(rule.get("form", "")) and \
                polymorphism == "MONOMORPHIC_NO_VARIABLES":
            violations.append((name, "signature has type variables but polymorphism is "
                                     "graded MONOMORPHIC"))
        if not has_type_variables(rule.get("form", "")) and active and \
                polymorphism not in ("MONOMORPHIC_NO_VARIABLES", "DESIGN_RESOLUTION",
                                     None):
            violations.append((name, f"no type variables in the signature but polymorphism "
                                     f"is graded {polymorphism}"))

        # 6. no upgrade of intent into observation
        for field, grade in (("signature_grade", signature),
                             ("polymorphism_grade", polymorphism)):
            if grade is None or behaviour is None:
                continue
            if AUTHORITY.get(grade, 0) > AUTHORITY.get(behaviour, 0):
                violations.append((name, f"{field}={grade} claims more authority than "
                                         f"behavior_grade={behaviour}"))

    report = {"contract": CONTRACT.name, "rules_checked": len(rules),
              "violations": [{"rule": r, "violation": v} for r, v in violations]}
    (CONTRACT.parent / "v2_1_evidence_audit.json").write_text(
        json.dumps(report, indent=1))

    if not violations:
        print(f"evidence discipline holds across {len(rules)} rules:")
        print("  no COMPATIBLE-only rule is required of the implementation")
        print("  no UNRESOLVED rule is active")
        print("  every DESIGN_RESOLUTION has a rationale")
        print("  every OBSERVED behaviour cites evidence")
        print("  every polymorphic signature carries its own grade")
        print("  no rule upgrades design intent to observation")
        return 0
    print(f"EVIDENCE DISCIPLINE VIOLATED: {len(violations)}\n")
    for name, violation in violations:
        print(f"  {name:22} {violation}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
