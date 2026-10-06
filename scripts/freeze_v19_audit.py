"""Write the v1.9 diagnostic pre-freeze manifest (before any v1.9 measurement).

Pins the audit protocol (sections 1 to 13), the tracer, the audit, the
development driver and analysis, the tests, and every v1.7/v1.8 file the
diagnosis reads. The development workers refuse to run if any pinned file
changes.
"""
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from cora_arc2026 import v17_compiler as X                        # noqa: E402

PINNED = (
    "docs/CORA_TTI_ENGINE_STABILITY_AUDIT_v1.9.md",
    "cora_arc2026/v19_trace.py",
    "cora_arc2026/v19_audit.py",
    "scripts/v19_audit_dev.py",
    "scripts/v19_audit_analyze.py",
    "tests/test_v19_audit.py",
    "cora_arc2026/v18_proposer.py",
    "cora_arc2026/v17_compiler.py",
    "scripts/v18_corpus.py",
    "scripts/v18_prospective.py",
    "outputs/tti/v18_frozen_d.json",
    "outputs/tti/v18_prospective_exclusion.json",
    "outputs/tti/v18_prospective_rows.jsonl",
    "outputs/tti/v18_dev_rows.jsonl",
    "outputs/tti/no_oracle_proposer_v18_manifest.json",
)


def sha(path):
    return hashlib.sha256(open(os.path.join(HERE, path), "rb").read()).hexdigest()


def main():
    out = os.path.join(HERE, "outputs", "tti", "v19_audit_prefreeze_manifest.json")
    head = subprocess.run(["git", "-C", HERE, "rev-parse", "HEAD"], capture_output=True,
                          text=True).stdout.strip()
    man = {"status": "DIAGNOSTIC_PREFREEZE: protocol sections 1-13, before any v1.9 measurement",
           "files": {p: sha(p) for p in PINNED},
           "k_identity": X.k_identity(),
           "seed_ranges": {"development": 870_000_000, "prospective_reserved": 880_000_000},
           "parent_head": head}
    with open(out, "w") as fh:
        json.dump(man, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(hashlib.sha256(open(out, "rb").read()).hexdigest())


if __name__ == "__main__":
    main()
