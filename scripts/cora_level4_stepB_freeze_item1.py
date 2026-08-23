"""Freeze Step-B item 1: inventory + K1 lattice + witness generator.

Emits the three machine-readable artifacts, requires every gate green, and
pins everything. After this freeze the constructor inventory, the K1
lattice, the witness generator and their meta-families are IMMUTABLE (the
design's rule: K2 is not widened or narrowed after the fact; a weak-looking
constructor is a result, not a defect to fix).

Gates, all mechanical, all required:
    1. the Step-B design document still matches its pinned hash
    2. the forbidden-shapes audit verdict is PASS (report rewritten)
    3. the synthetic unit tests pass (pytest, this repository, no cluster
       or corpus file is readable by them beyond what they manufacture)
    4. double generation of every artifact is byte-identical
    5. the frozen leak checker finds nothing in the emitted artifacts

Output: outputs/cora_breakthrough/level4_stepB_inventory.json,
level4_stepB_k1_lattice.json, level4_stepB_witnesses.json,
level4_stepB_item1_freeze.json (+ level4_stepB_item1_hash.txt pin).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"
sys.path.insert(0, str(ROOT))

DESIGN = ROOT / "docs" / "CORA_LEVEL4_STEPB_DESIGN.md"
DESIGN_PIN = OUT / "level4_stepB_design_hash.txt"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(msg: str) -> int:
    print(f"FREEZE REFUSED: {msg}")
    return 1


def main() -> int:
    # gate 1: design pin
    pinned = DESIGN_PIN.read_text().split()[0]
    actual = sha(DESIGN.read_bytes())
    if pinned != actual:
        return fail(f"design hash drift: pinned {pinned[:16]} != {actual[:16]}")
    print(f"design pin verified            {actual[:16]}")

    # gate 2: audit
    spec = importlib.util.spec_from_file_location(
        "stepB_audit", ROOT / "scripts" / "cora_level4_stepB_audit.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    if audit.main(write=True) != 0:
        return fail("forbidden-shapes audit did not pass")

    # gate 3: unit tests
    proc = subprocess.run(
        [sys.executable, "-m", "pytest",
         str(ROOT / "tests" / "test_level4_stepB_item1.py"), "-q"],
        cwd=ROOT, capture_output=True, text=True)
    tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    print(f"unit tests                     {tail}")
    if proc.returncode != 0:
        print(proc.stdout[-2000:])
        return fail("unit tests failed")

    # gate 4: byte-deterministic double generation
    from level4_stepB import k2_inventory as I
    from level4_stepB import k1_lattice as L
    from level4_stepB import witnesses as W

    def artifacts():
        inventory = json.dumps(I.inventory_record(), indent=1, sort_keys=True,
                               default=str)
        lattice = json.dumps(L.lattice_record(), indent=1, sort_keys=True)
        witness = json.dumps(W.witness_set(I.closure(), I.resolver()),
                             indent=1, sort_keys=True, default=str)
        return inventory, lattice, witness

    first, second = artifacts(), artifacts()
    if any(a != b for a, b in zip(first, second)):
        return fail("double generation not byte-identical")
    inventory, lattice, witness = first
    names = ("level4_stepB_inventory.json", "level4_stepB_k1_lattice.json",
             "level4_stepB_witnesses.json")
    for name, text in zip(names, first):
        (OUT / name).write_text(text)
    print(f"artifacts written              {', '.join(names)}")

    # gate 5: leak scan over the emitted artifacts
    spec2 = importlib.util.spec_from_file_location(
        "leak_check", ROOT / "scripts" / "cora_level4_leak_check.py")
    leak = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(leak)
    seal = json.loads(leak.SEAL.read_text())
    targets = leak.sealed_hashes(seal)
    forbidden = leak.forbidden_names()
    findings = []
    for name in names + ("level4_stepB_audit.json",):
        findings.extend(leak.scan_file(OUT / name, targets, forbidden))
    if findings:
        for f in findings:
            print("  LEAK", f)
        return fail(f"{len(findings)} leak finding(s) in emitted artifacts")
    print(f"leak scan over artifacts       0 findings "
          f"({len(forbidden)} forbidden names)")

    # the freeze record
    package_files = sorted((ROOT / "level4_stepB").glob("*.py"))
    executables = package_files + [
        ROOT / "scripts" / "cora_level4_stepB_audit.py",
        ROOT / "scripts" / "cora_level4_stepB_freeze_item1.py",
        ROOT / "tests" / "test_level4_stepB_item1.py"]
    record = {
        "gate": "Step-B item-1 freeze: inventory + K1 lattice + witnesses",
        "design_document_sha256": actual,
        "immutability": ("the constructor inventory, the K1 lattice, the "
                         "witness generator and their meta-families are "
                         "frozen; they may not be widened, narrowed or "
                         "re-tuned after this point, whatever the Step-B "
                         "run later shows"),
        "executables": {p.name: sha(p.read_bytes()) for p in executables},
        "artifacts": {name: sha(text.encode())
                      for name, text in zip(names, first)},
        "audit_report_sha256": sha((OUT / "level4_stepB_audit.json").read_bytes()),
        "counts": {
            "schemas": len(I.SCHEMAS),
            "families": len(I.FAMILIES),
            "ground_instances": I.inventory_record()["instance_count"],
            "type_universe": len(I.closure()),
            "k1_candidates": len(L.subsets()),
            "witness_contexts": W.BOUNDS["contexts"],
        },
        "unit_tests": tail,
        "depends_on": {
            "blind_bundle": "level4_bundle_freeze.json",
            "design_pin": "level4_stepB_design_hash.txt",
        },
    }
    text = json.dumps(record, indent=1, sort_keys=True)
    (OUT / "level4_stepB_item1_freeze.json").write_text(text)
    digest = sha(text.encode())
    (OUT / "level4_stepB_item1_hash.txt").write_text(digest + "\n")
    print(f"\nITEM 1 FROZEN")
    print(f"freeze record sha256 = {digest}")
    for key, value in record["counts"].items():
        print(f"  {key:20} {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
