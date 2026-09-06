"""Freeze the corrected-census manifest (directive section 11).

Every pinned value is READ FROM THE LIVE CODE, never retyped, so a manifest can
never claim a hash the executable does not have. The runner then reads every
experimental setting back out of this manifest; nothing scientific is hashed
here and executed from a separate constant.

Refuses to run unless the worktree is clean, so the pinned commit is the code
that will execute.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI     # noqa: E402
from cora_tti import constructive_probes as CP                   # noqa: E402
from cora_tti import constructive_v2c as V2C                     # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import meta_baseline as MB                         # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

OUT = ROOT / "outputs" / "tti" / "constructive_v2_corrected"
DOCS = ROOT / "docs"

parser = argparse.ArgumentParser()
parser.add_argument("--attempts-per-family", type=int, default=128)
parser.add_argument("--seed-namespace", type=int, default=5_300_000)
parser.add_argument("--allow-dirty", action="store_true",
                    help="diagnostics only; a real freeze requires a clean tree")
args = parser.parse_args()


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*cmd) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *cmd],
                          capture_output=True, text=True, check=True).stdout.strip()


dirty = git("status", "--porcelain")
if dirty and not args.allow_dirty:
    raise SystemExit(f"worktree is dirty; commit before freezing:\n{dirty}")

config = MB.BaselineConfig()
exclusion = ROOT / "outputs" / "tti" / "constructive_v1_1_target_exclusion.json"
exclusion_doc = json.loads(exclusion.read_text())

manifest = {
    "manifest": "CORA-TTI corrected feasibility census (v2c)",
    "frozen_before": "the first attempt of the corrected census",
    "supersedes_nothing": ("the original 120-attempt census stands as executed; its "
                           "family-coverage decision remains NO-GO and this run cannot "
                           "convert it into a GO"),
    "prelaunch_amendment": {
        "path": "docs/CORA_TTI_V2C_PRELAUNCH_AMENDMENT.md",
        "sha256": sha_file(DOCS / "CORA_TTI_V2C_PRELAUNCH_AMENDMENT.md")},
    "evidence_status": {
        "path": "docs/CORA_TTI_V2_EVIDENCE_STATUS.md",
        "sha256": sha_file(DOCS / "CORA_TTI_V2_EVIDENCE_STATUS.md")},

    #  ---- the research question and its fixed scope (unchanged) ----
    "families": {"training": [[0, 0], [1, 0], [0, 1], [1, 1], [0, 0, 0]],
                 "structural_holdout": [[2], [2, 1]]},
    "banned_target_families": CV.vocab()["banned_target_families"],
    "holdout_families": CV.vocab()["holdout_families"],
    "attempts_per_family": int(args.attempts_per_family),
    "seed_schedule": {"namespace": int(args.seed_namespace),
                      "family_stride": 2_000_003, "attempt_stride": 7919,
                      "formula": "namespace + family_index*family_stride + attempt*attempt_stride",
                      "note": "distinct stride per family index; no two families share a schedule"},

    #  ---- the demonstration protocol (read by the admission law) ----
    "generation": dict(V2C.DEFAULT_GENERATION),

    #  ---- admission ----
    "admission": {
        "requirements": "R1-R12 of the v2 directive, with the section-B amendment",
        "min_defined_probes": 1,
        "rejection_codes": list(V2C.REJECTION_CODES_V2C),
        "ablation_outcomes": list(V2C.ABLATION_OUTCOMES),
        "infrastructure_namespace": V2C.INFRA_PREFIX},

    #  ---- the one baseline reasoner ----
    "baseline_config": config.to_json(),
    "baseline_config_digest": config.digest(),
    "trace_config_digest": MB.trace_config_digest(config),
    "baseline_enumeration": {
        "hypothesis_set": "complete single-block product of the frozen terminals",
        "size": len(MB.hypothesis_space(config)),
        "set_equal_to_actual_search": True,
        "evidence": "outputs/tti/constructive_v2_corrected/baseline_enumeration_identity.json",
        "ordering_differs_from_actual_search": True,
        "work_limit": "fixed: all enumerated schemas; wall clock is an operational safeguard only"},

    #  ---- fitter ----
    "fitter_identity": SF.fitter_identity(),
    "fitter_options_strict": SF.fitter_options(True),
    "fitter_options_inspection": SF.fitter_options(False),
    "fitter_statuses": list(SF.FIT_STATUSES),
    "key_codec": "raw descriptor values as dictionary keys; typed JSON for serialization; no eval",

    #  ---- probes ----
    "probe_config": CP.probe_config(),
    "probe_set_digest": CP.probe_manifest()["probe_set_digest"],
    "probe_config_sha256": hashlib.sha256(
        json.dumps(CP.probe_config(), sort_keys=True).encode()).hexdigest(),

    #  ---- historical exclusion ----
    "historical_exclusion": {
        "path": "outputs/tti/constructive_v1_1_target_exclusion.json",
        "sha256": sha_file(exclusion),
        "unique_digests": exclusion_doc["unique_digests"],
        "derived_from": exclusion_doc["derivation"]},

    #  ---- budgets and resources ----
    "budgets": {"per_target_s": 300.0,
                "note": ("a per-target wall clock is an operational safeguard; if it fires the "
                         "attempt is recorded as a checker failure (generation_timeout), never "
                         "as a scientific property of the target")},
    "resource_limits": {"workers": 1, "nice": 15, "blas_threads": 1,
                        "note": "a separate live experiment has CPU priority on this host"},

    #  ---- environment and code ----
    "environment": {"PYTHONHASHSEED": "0", "python": platform.python_version(),
                    "numpy": np.__version__},
    "code_hashes": V2C.code_hashes_v2c(),
    "checker_failure_codes": list(V2C.CHECKER_FAILURE_CODES),
    "code_hash": V2C.code_hash_v2c(),
    "engine": {"meta_ast.py": sha_file(Path(M.__file__)),
               "meta_induction.py": sha_file(Path(MI.__file__))},
    "reused_v1_1_modules": {
        name: sha_file(ROOT / "cora_tti" / name)
        for name in ("constructive_vocabulary.py", "constructive_probes.py",
                     "constructive_dataset.py")},
    "v1_1_protocol_sha256": (ROOT / "outputs" / "tti"
                             / "constructive_protocol_manifest_hash.txt").read_text().split()[0],
    "original_v2_manifest_sha256": sha_file(
        ROOT / "outputs" / "tti" / "constructive_v2_feasibility_manifest.json"),
    "original_v2_results_sha256": sha_file(
        ROOT / "outputs" / "tti" / "constructive_v2_feasibility_results.json"),
    "git_commit": git("rev-parse", "HEAD"),
    "dirty_tree": bool(dirty),

    #  ---- declarations ----
    "declaration": ("Method development on disposable synthetic fixtures. Produces no "
                    "training, validation or test rows for any model, uses no DEV or "
                    "HOLDOUT ARC data, and reads nothing from the live Step-B experiment."),
    "output_schema": {
        "attempts": "outputs/tti/constructive_v2_corrected/attempts.jsonl, one JSON object "
                    "per attempt including every failure",
        "admitted": "outputs/tti/constructive_v2_corrected/admitted/<family>_<attempt>.json",
        "results": "outputs/tti/constructive_v2_corrected/results.json",
        "execution": "outputs/tti/constructive_v2_corrected/execution_record.json",
        "units": ["attempt", "unique schema", "concrete instantiation",
                  "demonstration bundle"]},
}

OUT.mkdir(parents=True, exist_ok=True)
text = json.dumps(manifest, indent=1, sort_keys=True)
(OUT / "manifest.json").write_text(text)
digest = hashlib.sha256(text.encode()).hexdigest()
(OUT / "manifest_hash.txt").write_text(digest + "\n")
print(json.dumps({"manifest_sha256": digest, "git_commit": manifest["git_commit"],
                  "dirty": manifest["dirty_tree"],
                  "attempts_per_family": manifest["attempts_per_family"],
                  "total_attempts": manifest["attempts_per_family"] * 7,
                  "baseline_config_digest": manifest["baseline_config_digest"][:16],
                  "fitter_identity": manifest["fitter_identity"][:16],
                  "exclusion_digests": manifest["historical_exclusion"]["unique_digests"],
                  "min_defined_probes": manifest["admission"]["min_defined_probes"]}, indent=1))
