"""Produce the blind inputs the Level-4 mechanism is allowed to read.

Two of the mechanism's natural inputs cannot be used as they stand. The
semantic contract names its inactive productions, and one of those names is
the sealed expectation. The concept registry carries the source task ids,
which the provenance firewall must keep out of the invention stage.

So the mechanism reads redacted views instead:

    the contract with every inactive production replaced by an opaque
    identifier and every rationale stripped, so the mechanism knows only
    that N names are forbidden, not what they are;

    the concept with its schema, types and cost, but no provenance.

The originals are untouched and remain the authority for certification,
which happens after an extension has already been proposed. The mapping from
opaque identifier back to real name, and from concept to source tasks, is
written to a firewall file that the invention stage never opens.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"
BLIND = OUT / "level4_mechanism_inputs"
FIREWALL = OUT / "level4_provenance_firewall.json"


def main():
    BLIND.mkdir(parents=True, exist_ok=True)
    contract = json.loads((OUT / "v2_1_semantic_contract_v2.json").read_text())
    registry = json.loads((OUT / "v21_concept_registry.json").read_text())

    # -- contract: opaque forbidden names, no rationales -------------------
    forbidden, mapping = [], {}
    for index, rule in enumerate(contract["layer_B_frozen_design"]["rules"]
                                 + contract["inactive_unresolved"]):
        if rule.get("active", False):
            continue
        opaque = f"forbidden_{index:02d}"
        forbidden.append(opaque)
        mapping[opaque] = rule["rule"]

    active = []
    for rule in contract["active_productions"] + \
            contract["layer_A_evidence_minimal"]["judgements"]:
        if not rule.get("active", True):
            continue
        active.append({"rule": rule["rule"], "form": rule.get("form", ""),
                       "behavior_grade": rule.get("behavior_grade"),
                       "signature_grade": rule.get("signature_grade"),
                       "polymorphism_grade": rule.get("polymorphism_grade")})

    blind_contract = {
        "note": ("Redacted view for the Level-4 invention mechanism. Inactive "
                 "productions appear only as opaque identifiers: the mechanism "
                 "knows how many names are forbidden, never which."),
        "active_productions": active,
        "forbidden_production_ids": forbidden,
        "forbidden_count": len(forbidden),
        "terminals": contract["terminals"]["types"],
        "polymorphism_policy": {
            "rule": contract["polymorphism_policy"]["rule"],
            "instantiations": {k: {"implemented_signature":
                                   v.get("implemented_signature")}
                               for k, v in
                               contract["polymorphism_policy"]["instantiations"].items()}},
        "kernel": contract["v21_kernel"]["rules"],
    }
    (BLIND / "contract_redacted.json").write_text(
        json.dumps(blind_contract, indent=1))

    # -- concept: no provenance -------------------------------------------
    blind_concepts, provenance = {}, {}
    for name, concept in registry.items():
        blind_concepts[name] = {k: v for k, v in concept.items()
                                if k not in ("provenance",
                                             "source_program_sha256")}
        provenance[name] = {"provenance": concept["provenance"],
                            "source_program_sha256":
                                concept["source_program_sha256"]}
    (BLIND / "concepts_redacted.json").write_text(
        json.dumps(blind_concepts, indent=1))

    FIREWALL.write_text(json.dumps({
        "warning": ("BEHIND THE PROVENANCE FIREWALL. The Level-4 invention "
                    "stage must never read this file. It is opened only by "
                    "the certification stage, after an extension has already "
                    "been proposed."),
        "forbidden_name_map": mapping,
        "concept_provenance": provenance}, indent=1))

    print(f"blind inputs written to {BLIND.name}/")
    print(f"  active productions exposed: {len(active)}")
    print(f"  forbidden productions exposed as opaque ids: {len(forbidden)}")
    print(f"  firewall file: {FIREWALL.name} (never a mechanism input)")
    for path in sorted(BLIND.glob("*.json")):
        print(f"  {path.name} sha256 "
              f"{hashlib.sha256(path.read_bytes()).hexdigest()[:16]}")


if __name__ == "__main__":
    sys.exit(main())
