"""Write and pin the Step-B RUN MANIFEST, before the single run.

The design (pin 28cc8734330345bf...) requires "a Step-B run manifest
pinning every hash (including this document's) before the single run".
This script refuses to write unless every gate it cites is green, and it
pins: the design, the item-1 freeze and its three artifacts, the Step-A
output and A.1 artifact, the Step-A run manifest, the blind bundle, every
Step-B executable (runner, enumerator, audits, gates, tests), the audit
and gate reports, the frozen enumeration bounds, the search limits, and
the protocol the runner implements (so the protocol cannot drift from the
executable without the runner's own hash changing).

The runner, started with --require-manifest, verifies that the manifest
matches its pin AND that the manifest cites the runner's own hash.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "cora_breakthrough"
INPUTS = OUT / "level4_mechanism_inputs"
sys.path.insert(0, str(ROOT))

from level4_blind_runtime import search as SEARCH      # noqa: E402
from level4_stepB import candidates as CA              # noqa: E402
from level4_stepB import witnesses as W                # noqa: E402

import importlib.util                                  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "stepB_runner", ROOT / "scripts" / "cora_level4_stepB_run.py")
RUN = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RUN)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(msg: str) -> int:
    print(f"MANIFEST REFUSED: {msg}")
    return 1


def main() -> int:
    design = ROOT / "docs" / "CORA_LEVEL4_STEPB_DESIGN.md"
    design_pin = (OUT / "level4_stepB_design_hash.txt").read_text().split()[0]
    if sha(design) != design_pin:
        return fail("design drift")
    item1_pin = (OUT / "level4_stepB_item1_hash.txt").read_text().split()[0]
    if sha(OUT / "level4_stepB_item1_freeze.json") != item1_pin:
        return fail("item-1 freeze drift")
    freeze = json.loads((OUT / "level4_stepB_item1_freeze.json").read_text())
    for name, digest in freeze["artifacts"].items():
        if sha(OUT / name) != digest:
            return fail(f"item-1 artifact drift: {name}")
    for name, digest in freeze["executables"].items():
        path = next(p for p in (ROOT / "level4_stepB" / name, ROOT / "scripts" / name,
                                ROOT / "tests" / name) if p.exists())
        if sha(path) != digest:
            return fail(f"item-1 executable drift: {name}")

    audit = json.loads((OUT / "level4_stepB_audit.json").read_text())
    runner_audit = json.loads((OUT / "level4_stepB_runner_audit.json").read_text())
    gates = json.loads((OUT / "level4_stepB_gates.json").read_text())
    if audit["verdict"] != "PASS":
        return fail("package audit is not PASS")
    if runner_audit["verdict"] != "PASS":
        return fail("runner audit is not PASS")
    if not gates["passed"]:
        return fail("gates did not pass")
    if set(audit["modules"]) < {"candidates.py"}:
        return fail("package audit did not cover candidates.py")

    # executable identity: the gates and the runner audit must have
    # exercised exactly the files on disk now
    current = {
        "scripts/cora_level4_stepB_run.py": sha(ROOT / "scripts" / "cora_level4_stepB_run.py"),
        "level4_stepB/candidates.py": sha(ROOT / "level4_stepB" / "candidates.py"),
    }
    tested = gates.get("tested_executables", {})
    if tested.get("tested_runner_sha256") != current["scripts/cora_level4_stepB_run.py"]:
        return fail("gates did not test the current runner")
    if tested.get("tested_candidates_sha256") != current["level4_stepB/candidates.py"]:
        return fail("gates did not test the current candidates.py")
    if tested.get("tested_item1_freeze_sha256") != item1_pin:
        return fail("gates did not test the pinned item-1 freeze")
    if tested.get("tested_design_sha256") != design_pin:
        return fail("gates did not test the pinned design")
    audited = {row["path"]: row["sha256"]
               for row in runner_audit.get("audited_files_sha256", [])}
    for path, digest in current.items():
        if audited.get(path) != digest:
            return fail(f"runner audit did not audit the current {path}")
    if gates.get("diagnostic_only"):
        return fail("gates report is DIAGNOSTIC_ONLY")

    stepA_hash = (OUT / "level4_stepA_output_hash.txt").read_text().split("\n")[0].strip()
    stepA1_pin = (OUT / "level4_stepA1_hash.txt").read_text().split()[0]
    if sha(OUT / "level4_stepA1_analysis.json") != stepA1_pin:
        return fail("A.1 drift")
    stepA_manifest_pin = (OUT / "level4_stepA_run_manifest_hash.txt").read_text().split()[0]
    if sha(OUT / "level4_stepA_run_manifest.json") != stepA_manifest_pin:
        return fail("Step-A run manifest drift")

    executables = {
        "scripts/cora_level4_stepB_run.py": ROOT / "scripts" / "cora_level4_stepB_run.py",
        "level4_stepB/candidates.py": ROOT / "level4_stepB" / "candidates.py",
        "scripts/cora_level4_stepB_runner_audit.py":
            ROOT / "scripts" / "cora_level4_stepB_runner_audit.py",
        "scripts/cora_level4_stepB_audit.py": ROOT / "scripts" / "cora_level4_stepB_audit.py",
        "scripts/cora_level4_stepB_gates.py": ROOT / "scripts" / "cora_level4_stepB_gates.py",
        "scripts/cora_level4_stepB_manifest.py": Path(__file__).resolve(),
        "tests/test_level4_stepB_item2.py": ROOT / "tests" / "test_level4_stepB_item2.py",
        "scripts/cora_level4_stepA_extract.py":
            ROOT / "scripts" / "cora_level4_stepA_extract.py",
    }
    manifest = {
        "stage": "Level 4 Step B: run manifest",
        "frozen_before": ("the single run over every eligible Step-A cluster. "
                          "Nothing pinned here may change once that run starts; "
                          "the runner refuses to start unless its own hash is "
                          "the one pinned below"),
        "design_document_sha256": design_pin,
        "item1_freeze_sha256": item1_pin,
        "item1_artifacts": freeze["artifacts"],
        "item1_executables": freeze["executables"],
        "stepA_output_hash": stepA_hash,
        "stepA1_analysis_sha256": stepA1_pin,
        "stepA_run_manifest_sha256": stepA_manifest_pin,
        "bundle_freeze_sha256": sha(OUT / "level4_bundle_freeze.json"),
        "blind_runtime": {p.name: sha(p) for p in
                          sorted((ROOT / "level4_blind_runtime").glob("*.py"))},
        "mechanism_inputs": {p.name: sha(p) for p in sorted(INPUTS.glob("*"))},
        "stepB_executables": {k: sha(v) for k, v in executables.items()},
        "gate_artifacts": {
            "level4_stepB_audit.json": sha(OUT / "level4_stepB_audit.json"),
            "level4_stepB_runner_audit.json": sha(OUT / "level4_stepB_runner_audit.json"),
            "level4_stepB_gates.json": sha(OUT / "level4_stepB_gates.json"),
        },
        "executable_identity": {
            "current": current,
            "gates_tested": {k: v for k, v in tested.items()
                             if k != "tested_blind_runtime"},
            "runner_audit_audited": audited,
            "rule": "manifest refused unless current == gates_tested == runner_audit_audited",
        },
        "gate_summary": {
            "package_audit": audit["verdict"],
            "package_audit_modules": audit["modules"],
            "runner_audit": runner_audit["verdict"],
            "runner_audit_files": runner_audit["files"],
            "gates_passed": gates["passed"],
            "protocol_checks": gates["protocol"]["checks"],
            "loo_fidelity": gates["loo_fidelity"]["passed"],
            "neutrality": gates["neutrality"]["checks"],
            "determinism": gates["determinism"]["identical"],
            "determinism_deadline_hits": gates["determinism"]["deadline_hits_in_both_runs"],
            "checkpoint_resume": gates["checkpoint_resume"]["passed"],
            "checkpoint_resume_checks": gates["checkpoint_resume"]["checks"],
        },
        "enumeration_bounds": dict(CA.BOUNDS),
        "resolution_policy": ("exhaustive after witness-fingerprint deduplication: "
                              "every witness-equivalence-class representative of every "
                              "proposing source is resolution-tested; no cap, "
                              "no early stop"),
        "labels_at_generation": dict(CA.LABELS),
        "witness_seed": W.SEED,
        "witness_bounds": dict(W.BOUNDS),
        "search_limits_unchanged": {"max_depth": SEARCH.MAX_DEPTH,
                                    "per_type_cap": SEARCH.PER_TYPE_CAP,
                                    "max_candidates": SEARCH.MAX_CANDIDATES,
                                    "budget_seconds": SEARCH.budget_s()},
        "protocol": {
            "cluster_order": "(-N_distinct_sources, -N_records, canonical(cluster_key))",
            "cluster_input_to_generation": "the interface (frontier_type, goal_type) only",
            "candidate_lanes": {
                "K2": "inventory instances + registry expression formers; "
                      "label NEW_SEMANTIC_PRODUCTION",
                "K1": "frozen registry bodies x 31 guard-relaxation learners; "
                      "label SLOT_LEARNER_REPAIR"},
            "proposal_K2": ("the source's failed frontier terms, deduplicated by "
                            "their values on the demonstration inputs, plugged "
                            "into the candidate's port; terminal parameters in "
                            "vocabulary order; induced parameters fitted by the "
                            "ordinary learners; the first exact fit on ALL "
                            "demonstrations is the proposal"),
            "proposal_K1": ("the ordinary unchanged search with the relaxed "
                            "learner installed, per (learner, source)"),
            "resolution": ("per (class representative, proposing source), EVERY "
                           "representative, in MDL-then-id order: unchanged search "
                           "on the full demonstrations + leave-one-out by complete "
                           "rediscovery with only that candidate installed; "
                           "certified iff found, uses the candidate (K2), all folds pass"),
            "selection": "kept iff >= 2 certified distinct source tokens of a "
                         "proposing cluster; ties by MDL then lexicographic",
            "dedup": ("witness-equivalence classes: equal (lane, signature, "
                      "behaviour fingerprint over the frozen witness set, "
                      "learner); equality on a finite probe set is NOT a proof "
                      "of global denotational equivalence"),
            "no_early_stop": "every eligible cluster, every candidate, every "
                             "witness-equivalence class, every proposing source",
            "label_discipline": ("NEW_SEMANTIC_PRODUCTION is the K2 generation-lane "
                                 "label only; semantic novelty is decided by the "
                                 "separation certificate at certification"),
            "output_discipline": ("counts only to stdout; all records to files; "
                                  "output hash pinned by the runner at completion, "
                                  "before inspection; timing kept out of hashed files"),
            "not_computed_here": ["semantic separation certificate",
                                  "criteria 3, 5, 6", "E_transfer", "Lockbox"],
        },
        "prohibitions": ("no widening/narrowing of inventory, lattice or witnesses; "
                         "no human cluster selection; no early stop; no repair "
                         "after the fact; no reading of E_transfer, Promotion, "
                         "the Lockbox or the sealed expectation"),
    }
    text = json.dumps(manifest, indent=1, sort_keys=True)
    (OUT / "level4_stepB_run_manifest.json").write_text(text)
    digest = hashlib.sha256(text.encode()).hexdigest()
    (OUT / "level4_stepB_run_manifest_hash.txt").write_text(digest + "\n")
    print("STEP-B RUN MANIFEST FROZEN")
    print(f"manifest sha256 = {digest}")
    print(f"runner sha256   = {manifest['stepB_executables']['scripts/cora_level4_stepB_run.py']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
