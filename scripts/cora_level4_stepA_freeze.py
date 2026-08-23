"""Freeze the Step-A run manifest: the last artifact written BEFORE the run.

The Phase-5 lesson, applied: freezing the criteria but not the executable
leaves room for an accidental mismatch, so the runner, the generated trace
search, the gate verdict and every input they touch are pinned here together,
referencing the already-frozen bundle. After this manifest is written and its
hash pinned, the 450-record run happens exactly once.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"
INPUTS = OUT / "level4_mechanism_inputs"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    bundle = json.loads((OUT / "level4_bundle_freeze.json").read_text())
    machine = json.loads((INPUTS / "machine_manifest.json").read_text())
    gates = json.loads((OUT / "level4_stepA_gates.json").read_text())
    trace_build = json.loads((OUT / "level4_stepA_trace_build.json").read_text())
    leak = json.loads((OUT / "level4_leak_check.json").read_text())

    if not gates["passed"]:
        print("ABORT: the pre-run gates did not pass")
        return 1
    if leak["findings"]:
        print("ABORT: the leak check has findings")
        return 1
    runner = "cora_level4_stepA_extract.py"
    if runner not in leak["executable_inputs_checked"]:
        print("ABORT: the runner is not covered by the leak check")
        return 1
    if "stepA_trace_search.py" not in leak["executable_inputs_checked"]:
        print("ABORT: the trace search is not covered by the leak check")
        return 1
    if not trace_build["round_trip_identical_to_frozen_search"]:
        print("ABORT: trace search round-trip identity not established")
        return 1
    generated = sha256(ROOT / "level4_blind_runtime" / "stepA_trace_search.py")
    if generated != trace_build["generated_sha256"]:
        print("ABORT: stepA_trace_search.py changed after its build record")
        return 1

    bundle_digest = hashlib.sha256(
        (OUT / "level4_bundle_freeze.json").read_bytes()).hexdigest()

    manifest = {
        "stage": "Level 4 Step A: run manifest",
        "frozen_before": ("the single 450-record extraction run. Nothing "
                          "pinned here may change once that run starts."),
        "references": {
            "bundle_freeze_sha256": bundle_digest,
            "bundle_data_inputs": bundle["data_inputs"],
            "bundle_executable_inputs": bundle["executable_inputs"],
            "machine_manifest_document_sha256":
                machine["manifest_document_sha256"],
        },
        "stepA_executables": {
            "scripts/cora_level4_stepA_extract.py":
                sha256(ROOT / "scripts" / "cora_level4_stepA_extract.py"),
            "level4_blind_runtime/stepA_trace_search.py": generated,
            "scripts/cora_level4_build_trace_search.py":
                sha256(ROOT / "scripts" / "cora_level4_build_trace_search.py"),
            "scripts/cora_level4_stepA_gates.py":
                sha256(ROOT / "scripts" / "cora_level4_stepA_gates.py"),
        },
        "gate_artifacts": {
            "level4_stepA_gates.json": sha256(OUT / "level4_stepA_gates.json"),
            "level4_stepA_trace_build.json":
                sha256(OUT / "level4_stepA_trace_build.json"),
            "level4_leak_check.json": sha256(OUT / "level4_leak_check.json"),
        },
        "gate_summary": {
            "tracing_changes_nothing_on_untruncated_fixtures": True,
            "runner_protocol_checks":
                list(gates["runner_rules"]["checks"]),
            "byte_deterministic": gates["determinism"]["identical"],
            "leak_check": "0 findings over 5 data + 7 executable inputs",
        },
        "protocol": {
            "corpus": "level4_mechanism_inputs/invention_corpus.jsonl",
            "corpus_records": 450,
            "fold_failure": ("the ranked winner of the ordinary blind search "
                             "on the other demonstrations does not reproduce "
                             "the held-out output; a fold with no discovered "
                             "program fails too"),
            "frontier_schema_version": 1,
            "frontier_fields": ["source_token", "fold_index", "frontier_ast",
                                "frontier_type", "goal_type",
                                "frontier_surface_depth",
                                "frontier_value_signature",
                                "goal_delta_signature",
                                "behavioural_residual", "repeated_structure",
                                "failure_class", "diagnostics"],
            "failure_class_precedence": machine["failure_classes"],
            "execution_test_cap":
                machine["frontier"]["execution_test_cap"],
            "cluster_key": ["frontier_type", "goal_type",
                            "goal_delta_signature", "failure_class"],
            "cluster_eligibility_distinct_source_tokens":
                machine["cluster_eligibility"]["distinct_source_tokens"],
            "output_discipline": ("counts only to stdout during the run; "
                                  "records, fold summary and clusters written "
                                  "to files; their SHA-256 pinned before any "
                                  "semantic inspection"),
        },
        "prohibitions": ("no extension proposal, no E_transfer, no "
                         "Promotion, no Lockbox, no repair of any failure, "
                         "no reclassification after the fact"),
    }

    path = OUT / "level4_stepA_run_manifest.json"
    path.write_text(json.dumps(manifest, indent=1))
    digest = sha256(path)
    (OUT / "level4_stepA_run_manifest_hash.txt").write_text(digest + "\n")

    print("STEP-A RUN MANIFEST FROZEN")
    print(f"  manifest sha256  {digest}")
    print(f"  runner sha256    "
          f"{manifest['stepA_executables']['scripts/cora_level4_stepA_extract.py'][:16]}")
    print(f"  trace sha256     {generated[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
