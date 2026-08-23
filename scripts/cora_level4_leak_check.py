"""Does anything the Level-4 mechanism reads leak the sealed expectation?

The first version of the Level-4 manifest declared that a particular
expectation must be withheld and then wrote that expectation into itself, in
plaintext, three times. This check exists so that failure cannot recur
silently.

It verifies, against every file the mechanism is allowed to read:

    no sealed term appears
    no ARC task id appears
    no worked example of a candidate completion appears

The sealed terms are never stored here in plaintext. The seal file holds
only their hashes, so this script hashes candidate n-grams from each input
and compares. A leak is therefore detectable without the detector knowing
the answer.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"
SEAL = OUT / "level4_withheld_expectation_seal.json"

#: Everything the Level-4 mechanism is permitted to READ. The raw contract
#: and concept registry are NOT here: they name inactive productions and
#: carry source task ids, so the mechanism reads redacted views instead.
DATA_INPUTS = [
    ROOT / "docs" / "CORA_LEVEL4_MANIFEST.md",
    OUT / "level4_mechanism_inputs" / "contract_redacted.json",
    OUT / "level4_mechanism_inputs" / "concepts_redacted.json",
    OUT / "level4_mechanism_inputs" / "machine_manifest.json",
    OUT / "level4_mechanism_inputs" / "invention_corpus.jsonl",
]

#: Everything the Level-4 mechanism EXECUTES. Checking only the data would
#: leave the code unchecked, and the code is where the excluded evaluator
#: names and bodies live. A sanitized corpus imported alongside the ordinary
#: runtime is not a firewall. The Step-A runner is executable input too: it
#: is the program that turns the frozen inputs into frontier records, so it
#: is held to the same lexical standard as the runtime it drives.
EXECUTABLE_INPUTS = sorted((ROOT / "level4_blind_runtime").glob("*.py")) + [
    ROOT / "scripts" / "cora_level4_stepA_extract.py",
]

#: Names that must not appear in anything the mechanism reads or runs. Built
#: from the frozen admission, so this cannot drift from K_L4*.
A01 = OUT / "level4_baseline_admissibility_v2.json"


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def hashed(text: str) -> str:
    return hashlib.sha256(normalise(text).encode()).hexdigest()


def sealed_hashes(seal: dict) -> set:
    targets = {v for k, v in seal.items()
               if k.endswith("_sha256") and isinstance(v, str)}
    targets |= set(seal.get("withheld_terms_individual_sha256", []))
    return targets


def candidate_spans(text: str):
    """Word n-grams up to length 4, covering compounds and type arrows."""
    words = re.findall(r"[A-Za-z_\[\]>\-]+", text)
    for size in (1, 2, 3, 4):
        for index in range(len(words) - size + 1):
            yield " ".join(words[index:index + size])


def forbidden_names() -> set:
    """Production names that are not part of E_L4*, from the frozen record."""
    if not A01.exists():
        return set()
    admissibility = json.loads(A01.read_text())
    admitted = set(admissibility["K_L4_star"])
    allowed = set(admitted) | {n.split("@", 1)[0] for n in admitted}
    allowed |= {"Concept"}          # the abstraction mechanism, not a capability
    names = set()
    for row in admissibility.get("module_level_equivalence", {}).get(
            "added_by_level4", []):
        names.add(row)
    firewall = OUT / "level4_provenance_firewall.json"
    if firewall.exists():
        names |= set(json.loads(
            firewall.read_text()).get("forbidden_name_map", {}).values())
    return {n for n in names if n not in allowed and len(n) > 2}


def scan_file(path: Path, targets: set, forbidden: set) -> list:
    """Every leak kind, reported separately rather than as one verdict."""
    found = []
    text = path.read_text(errors="ignore")
    for span in candidate_spans(text):
        if hashed(span) in targets:
            found.append((path.name, "SEALED TERM PRESENT", hashed(span)[:12]))
    for task_id in sorted(set(re.findall(r"\b[0-9a-f]{8}\b", text))):
        found.append((path.name, "TASK ID PRESENT", task_id))
    for name in sorted(forbidden):
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])",
                     text):
            found.append((path.name, "FORBIDDEN PRODUCTION NAME", name))
    if path.suffix == ".md":
        for match in re.findall(
                r"`?[A-Z][A-Za-z]*\[[^\]]+\]\s*->\s*[A-Z][A-Za-z]*`?", text):
            found.append((path.name, "TYPE-TRANSITION EXAMPLE", match))
    return found


def main():
    if not SEAL.exists():
        print("no seal file; nothing to check against")
        return 1
    seal = json.loads(SEAL.read_text())
    targets = sealed_hashes(seal)
    forbidden = forbidden_names()

    data, executable = [], []
    for path in DATA_INPUTS:
        if path.exists():
            data.extend(scan_file(path, targets, forbidden))
    for path in EXECUTABLE_INPUTS:
        if path.exists():
            executable.extend(scan_file(path, targets, forbidden))
    findings = data + executable

    def by_kind(rows, kind):
        return [{"file": f, "detail": d} for f, k, d in rows if k == kind]

    report = {
        "gate": "Level-4 mechanism leak check",
        "scope": ("lexical and identifier test over everything the mechanism "
                  "reads AND everything it executes. This is NOT a claim of "
                  "semantic non-contamination: it proves no sealed term, task "
                  "id or excluded production NAME is present, not that the "
                  "environment carries no usable hint."),
        "data_inputs_checked": [p.name for p in DATA_INPUTS if p.exists()],
        "executable_inputs_checked": [p.name for p in EXECUTABLE_INPUTS
                                      if p.exists()],
        "forbidden_names_checked": len(forbidden),
        "sealed_lexeme_findings": by_kind(findings, "SEALED TERM PRESENT"),
        "task_id_findings": by_kind(findings, "TASK ID PRESENT"),
        "forbidden_production_name_findings": by_kind(
            findings, "FORBIDDEN PRODUCTION NAME"),
        "worked_transition_findings": by_kind(findings,
                                              "TYPE-TRANSITION EXAMPLE"),
        "findings": [{"file": f, "kind": k, "detail": d}
                     for f, k, d in findings],
    }
    (OUT / "level4_leak_check.json").write_text(json.dumps(report, indent=1))

    print(f"DATA INPUTS checked       {len(report['data_inputs_checked'])}: "
          f"{', '.join(report['data_inputs_checked'])}")
    print(f"EXECUTABLE INPUTS checked {len(report['executable_inputs_checked'])}"
          f": {', '.join(report['executable_inputs_checked'])}")
    print(f"forbidden production names checked: {len(forbidden)}")
    for label, key in (("sealed lexeme", "sealed_lexeme_findings"),
                       ("task id", "task_id_findings"),
                       ("forbidden production name",
                        "forbidden_production_name_findings"),
                       ("worked transition", "worked_transition_findings")):
        print(f"  {label:26} {len(report[key])}")

    if not findings:
        print("\nLEAK CHECK PASSED (lexical/identifier only)")
        return 0
    print(f"\nLEAK CHECK FAILED: {len(findings)} finding(s)\n")
    for name, kind, detail in findings:
        print(f"  {name:30} {kind:26} {detail}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
