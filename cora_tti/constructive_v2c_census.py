"""Corrected, prospectively frozen census runner (directive section 11).

Every experimental setting is READ FROM THE MANIFEST; nothing scientific is a
hard-coded constant here. The manifest is frozen (hash pinned, clean tree)
before the first attempt. The run is restart-safe: every attempt is appended
durably to attempts.jsonl as it completes, and a restart rebuilds the run-wide
identity state from that file and continues at the first unrecorded attempt.

Units of analysis, recorded separately on every row:
    attempt                        (family, attempt index, seed)
    unique schema                  canonical schema digest
    concrete instantiation         digest of the instantiated program
    demonstration bundle           digest of the rendered demonstrations

Usage
    PYTHONHASHSEED=<manifest value> OMP_NUM_THREADS=1 nice -n 15 \\
        python3 -m cora_tti.constructive_v2c_census
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_v2c as V2C                     # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import meta_baseline as MB                         # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

OUT = ROOT / "outputs" / "tti" / "constructive_v2_corrected"
MANIFEST = OUT / "manifest.json"
MANIFEST_HASH = OUT / "manifest_hash.txt"
ATTEMPTS = OUT / "attempts.jsonl"
ADMITTED_DIR = OUT / "admitted"
EXECUTION = OUT / "execution_records.jsonl"
RESULTS = OUT / "results.json"


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    pinned = MANIFEST_HASH.read_text().split()[0]
    actual = _sha_file(MANIFEST)
    if pinned != actual:
        raise RuntimeError(f"manifest hash {actual} != pinned {pinned}")
    return manifest


def seed_for(manifest: dict, family_index: int, attempt: int) -> int:
    schedule = manifest["seed_schedule"]
    return (int(schedule["namespace"]) + family_index * int(schedule["family_stride"])
            + attempt * int(schedule["attempt_stride"]))


def families_of(manifest: dict) -> list:
    return [tuple(f) for f in [*manifest["families"]["training"],
                               *manifest["families"]["structural_holdout"]]]


def load_exclusion(manifest: dict) -> set:
    path = ROOT / manifest["historical_exclusion"]["path"]
    actual = _sha_file(path)
    if actual != manifest["historical_exclusion"]["sha256"]:
        raise RuntimeError("historical exclusion set hash mismatch")
    doc = json.loads(path.read_text())
    return set(doc["digests"])


def existing_rows(manifest_sha: str) -> list:
    """Rows of THIS census only. A row written under a different manifest is a
    different experiment; resuming across one would let a single results.json
    report attempts from two protocols, so it is refused rather than skipped."""
    if not ATTEMPTS.exists():
        return []
    rows, foreign = [], []
    for line in ATTEMPTS.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("manifest_sha256") != manifest_sha:
            foreign.append(row.get("manifest_sha256"))
            continue
        rows.append(row)
    if foreign:
        raise RuntimeError(
            f"{len(foreign)} attempt rows in {ATTEMPTS} were written under a different "
            f"manifest ({sorted(set(foreign))[:2]}); move that file aside before running "
            f"this census, do not mix protocols in one result")
    return rows


def rebuild_state(manifest: dict, rows: list) -> V2C.CensusState:
    """Run-wide identity state, restored from the durable attempt log.

    The schema digest is taken from the row's own top-level field, which is
    written for EVERY attempt including one that raised, so a restart restores
    exactly the guard state a continuous run would have held."""
    state = V2C.CensusState(v1_exclusion=load_exclusion(manifest))
    for row in rows:
        units = row.get("units") or {}
        digest = units.get("schema_digest") or row.get("schema_digest") or ""
        state.record(digest=digest, regime=row["regime"], outcome=row["outcome"],
                     concrete_digest=units.get("concrete_digest"),
                     demo_digest=units.get("demo_bundle_digest"))
    return state


def _git_head() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:                                             # noqa: BLE001
        return "UNKNOWN"


def _resource_snapshot() -> dict:
    try:
        load1, load5, load15 = os.getloadavg()
    except OSError:
        load1 = load5 = load15 = None
    return {"loadavg_1_5_15": [load1, load5, load15], "pid": os.getpid(),
            "nice": os.nice(0), "omp_threads": os.environ.get("OMP_NUM_THREADS"),
            "cpu_count": os.cpu_count(), "host": platform.node()}


def run() -> dict:
    manifest = load_manifest()
    expected_hashseed = str(manifest["environment"]["PYTHONHASHSEED"])
    if os.environ.get("PYTHONHASHSEED") != expected_hashseed:
        raise RuntimeError(f"PYTHONHASHSEED must be {expected_hashseed!r} "
                           f"(is {os.environ.get('PYTHONHASHSEED')!r})")
    code_at_start = V2C.code_hashes_v2c()
    for name, pinned in manifest["code_hashes"].items():
        if code_at_start.get(name) != pinned:
            raise RuntimeError(f"code hash mismatch for {name}: run from the frozen commit")
    config = MB.BaselineConfig.from_json(manifest["baseline_config"])
    if config.digest() != manifest["baseline_config_digest"]:
        raise RuntimeError("baseline configuration digest differs from the manifest")
    if MB.trace_config_digest(config) != manifest["trace_config_digest"]:
        raise RuntimeError("trace configuration digest differs from the manifest")
    if SF.fitter_identity() != manifest["fitter_identity"]:
        raise RuntimeError("fitter identity differs from the manifest")
    #  the manifest records the fitter's scientific OPTIONS; check the live
    #  implementation actually runs under them, so a hashed option set can never
    #  be reported as executed while a different one ran
    if SF.fitter_options(True) != manifest["fitter_options_strict"] or \
            SF.fitter_options(False) != manifest["fitter_options_inspection"]:
        raise RuntimeError("live fitter options differ from the manifest")
    if dict(config.strict_options) != manifest["fitter_options_strict"]:
        raise RuntimeError("baseline strict options differ from the manifest fitter options")
    #  every generated schema, grid and probe comes from numpy's Generator, which
    #  carries no cross-version stream guarantee
    if np.__version__ != manifest["environment"]["numpy"]:
        raise RuntimeError(f"numpy {np.__version__} != manifest "
                           f"{manifest['environment']['numpy']}; the generator stream is "
                           f"not guaranteed across versions")
    if platform.python_version() != manifest["environment"]["python"]:
        raise RuntimeError(f"python {platform.python_version()} != manifest "
                           f"{manifest['environment']['python']}")

    OUT.mkdir(parents=True, exist_ok=True)
    ADMITTED_DIR.mkdir(exist_ok=True)
    manifest_sha = _sha_file(MANIFEST)
    rows = existing_rows(manifest_sha)
    done = {(r["family_text"], r["attempt"]) for r in rows}
    state = rebuild_state(manifest, rows)
    families = families_of(manifest)
    per_family = int(manifest["attempts_per_family"])
    budgets = dict(manifest["budgets"])
    min_defined = int(manifest["admission"]["min_defined_probes"])
    generation = dict(manifest["generation"])

    execution = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "git_head": _git_head(), "code_hashes_at_start": code_at_start,
                 "manifest_sha256": manifest_sha,
                 "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
                 "python": platform.python_version(), "numpy": np.__version__,
                 "resources_at_start": _resource_snapshot(),
                 "resumed_from_rows": len(rows)}
    #  appended, never overwritten: a restarted census keeps the provenance of
    #  every process that contributed attempts to it
    with EXECUTION.open("a") as handle:
        handle.write(json.dumps(execution, sort_keys=True) + "\n")

    started = time.monotonic()
    for family_index, family in enumerate(families):
        family_text = CV.family_text(family)
        regime = "structural_holdout" if CV.is_holdout_family(family) else "train_pool"
        for attempt in range(per_family):
            if (family_text, attempt) in done:
                continue
            seed = seed_for(manifest, family_index, attempt)
            schema = CD.sample_target(seed, family)
            t0 = time.monotonic()
            try:
                outcome, episode, evidence = V2C.evaluate_target_v2c(
                    schema, seed=seed, split="census", regime=regime,
                    allowed_families=[family], state=state, config=config,
                    budgets=budgets, row_index=attempt, min_defined_probes=min_defined,
                    generation=generation)
            except Exception as error:                            # noqa: BLE001
                outcome = f"{V2C.INFRA_PREFIX}{type(error).__name__}"
                episode, evidence = None, {"infra_error": repr(error)[:300], "units": {}}
                state.record(digest=CV.digest(schema), regime=regime, outcome=outcome,
                             concrete_digest=None, demo_digest=None)
            row = {"manifest_sha256": manifest_sha,
                   "family": list(family), "family_text": family_text, "attempt": attempt,
                   "seed": seed, "regime": regime, "outcome": outcome,
                   "schema_digest": CV.digest(schema),
                   "blocks": [[p, list(s), f] for p, s, f in CV.blocks_from_ast(schema)],
                   "units": evidence.get("units", {}),
                   "stage_times": evidence.get("stage_times", {}),
                   "scoped_fit": evidence.get("scoped_fit"),
                   "baseline": evidence.get("baseline"),
                   "witness_separation": evidence.get("witness_separation"),
                   "probe_coverage": evidence.get("probe_coverage"),
                   "irreducibility": evidence.get("irreducibility"),
                   "demo_diagnostic": evidence.get("demo_diagnostic"),
                   "leak_findings": evidence.get("leak_findings"),
                   "baseline_incompleteness": evidence.get("baseline_incompleteness"),
                   "baseline_truncated": (evidence.get("baseline") or {}).get("truncated"),
                   "baseline_complete": (evidence.get("baseline") or {}).get("complete"),
                   "truncated_by_wall_clock": evidence.get("truncated_by_wall_clock"),
                   "infra_error": evidence.get("infra_error"),
                   "baseline_config_digest": evidence.get("baseline_config_digest"),
                   "trace_config_digest": evidence.get("trace_config_digest"),
                   "code_hash": V2C.code_hash_v2c(),
                   "seconds": round(time.monotonic() - t0, 3)}
            if outcome == V2C.ADMITTED:
                path = ADMITTED_DIR / f"{family_text}_{attempt:04d}.json"
                path.write_text(json.dumps(episode, indent=1, sort_keys=True, default=str))
                row["episode_file"] = str(path.relative_to(OUT))
                row["episode_sha256"] = _sha_file(path)
                row["tfg_digest"] = episode["tfg_digest"]
            with ATTEMPTS.open("a") as handle:
                handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
            rows.append(row)
            done.add((family_text, attempt))
        counts = Counter(r["outcome"] for r in rows if r["family_text"] == family_text)
        print(f"{family_text:8} {dict(sorted(counts.items()))}", flush=True)

    return finalize(manifest, rows, state, execution, time.monotonic() - started)


def finalize(manifest: dict, rows: list, state: V2C.CensusState, execution: dict,
             seconds: float) -> dict:
    families = families_of(manifest)
    holdout = [tuple(f) for f in manifest["families"]["structural_holdout"]]
    report = {"manifest_sha256": _sha_file(MANIFEST), "families": {}, "units": state.units(),
              "attempts_per_family": int(manifest["attempts_per_family"])}
    for family in families:
        text = CV.family_text(family)
        frows = [r for r in rows if r["family_text"] == text]
        outcomes = Counter(r["outcome"] for r in frows)
        #  THREE categories, never two: a scientific verdict about the target, a
        #  failure of the checking machinery, and an uncaught exception. Only the
        #  first is evidence about the research question.
        infra = {k: v for k, v in outcomes.items() if k.startswith(V2C.INFRA_PREFIX)}
        checker = {k: v for k, v in outcomes.items() if k in V2C.CHECKER_FAILURE_CODES}
        scientific = {k: v for k, v in outcomes.items()
                      if not k.startswith(V2C.INFRA_PREFIX) and k not in V2C.CHECKER_FAILURE_CODES}
        admitted = [r for r in frows if r["outcome"] == V2C.ADMITTED]
        evaluated = sum(scientific.values())
        report["families"][text] = {
            "family": list(family), "attempts": len(frows),
            "scientifically_evaluated_attempts": evaluated,
            "admitted_attempts": len(admitted),
            "admitted_distinct_schemas": len({r["schema_digest"] for r in admitted}),
            "feasible": len(admitted) > 0,
            "no_admission_but_nothing_was_evaluated": evaluated == 0 and not admitted,
            "scientific_outcomes": dict(sorted(scientific.items())),
            "checker_failures": dict(sorted(checker.items())),
            "infrastructure_errors": dict(sorted(infra.items())),
            "target_wall_clock_truncations": sum(1 for r in frows
                                                 if r.get("truncated_by_wall_clock")),
            "baseline_truncations": sum(1 for r in frows if r.get("baseline_truncated")),
            "baseline_incomplete": checker.get("baseline_incomplete", 0),
            "irreducibility_inconclusive": checker.get("irreducibility_inconclusive", 0),
            "admitted_with_demonstration_only_reproducing_ablation": sum(
                1 for r in admitted
                if (r.get("irreducibility") or {}).get(
                    "demonstration_only_reproducing_ablations", 0) > 0),
            "seconds": round(sum(r["seconds"] for r in frows), 1)}
    fams = report["families"]
    #  a family that evaluated nothing is not evidence of infeasibility; it is a
    #  measurement that did not happen, and the gates say so explicitly
    report["families_with_no_evaluated_attempt"] = [
        k for k, v in fams.items() if v["no_admission_but_nothing_was_evaluated"]]
    report["gate_validity"] = {
        "all_families_evaluated_something": not report["families_with_no_evaluated_attempt"],
        "checker_failures_total": sum(sum(v["checker_failures"].values()) for v in fams.values()),
        "infrastructure_errors_total": sum(sum(v["infrastructure_errors"].values())
                                           for v in fams.values()),
        "note": ("a False gate means no admissible target was found among the attempts under "
                 "this generator and admission procedure; it is not a proof of impossibility")}
    report["decision_a_gates"] = {
        "g2_multi_block_target": any(v["feasible"] and len(v["family"]) > 1 for v in fams.values()),
        "g3_repeated_select_target": any(v["feasible"] and 2 in v["family"] for v in fams.values()),
        "g4_zero_select_block_in_multi_block_target": any(
            v["feasible"] and len(v["family"]) > 1 and 0 in v["family"] for v in fams.values()),
        "g5_both_holdout_families": all(fams[CV.family_text(f)]["feasible"] for f in holdout),
        "families_with_admissions": [k for k, v in fams.items() if v["feasible"]],
        "families_without_admissions": [k for k, v in fams.items() if not v["feasible"]],
    }
    report["units_recorded"] = {
        "attempts": len(rows),
        "unique_schemas": len({r["schema_digest"] for r in rows}),
        "unique_concrete_instantiations": len({(r.get("units") or {}).get("concrete_digest")
                                               for r in rows} - {None}),
        "unique_demonstration_bundles": len({(r.get("units") or {}).get("demo_bundle_digest")
                                             for r in rows} - {None}),
        "distinct_admitted_schemas": len({r["schema_digest"] for r in rows
                                          if r["outcome"] == V2C.ADMITTED}),
    }
    code_at_end = V2C.code_hashes_v2c()
    all_executions = [json.loads(line) for line in EXECUTION.read_text().splitlines() if line.strip()]
    report["execution"] = dict(
        execution, finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        code_hashes_at_end=code_at_end,
        code_unchanged_during_run=all(
            record["code_hashes_at_start"] == code_at_end for record in all_executions),
        processes_that_contributed=len(all_executions),
        all_process_records=all_executions,
        resources_at_end=_resource_snapshot(), seconds_this_process=round(seconds, 1))
    report["attempts_sha256"] = _sha_file(ATTEMPTS)
    RESULTS.write_text(json.dumps(report, indent=2, sort_keys=True))
    print("V2C_CENSUS_DONE", json.dumps(report["decision_a_gates"]), flush=True)
    return report


if __name__ == "__main__":
    run()
