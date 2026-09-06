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
EXECUTION = OUT / "execution_record.json"
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


def existing_rows() -> list:
    if not ATTEMPTS.exists():
        return []
    rows = []
    for line in ATTEMPTS.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def rebuild_state(manifest: dict, rows: list) -> V2C.CensusState:
    """Run-wide identity state, restored from the durable attempt log."""
    state = V2C.CensusState(v1_exclusion=load_exclusion(manifest))
    for row in rows:
        units = row.get("units") or {}
        state.record(digest=units.get("schema_digest") or "", regime=row["regime"],
                     outcome=row["outcome"], concrete_digest=units.get("concrete_digest"),
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

    OUT.mkdir(parents=True, exist_ok=True)
    ADMITTED_DIR.mkdir(exist_ok=True)
    rows = existing_rows()
    done = {(r["family_text"], r["attempt"]) for r in rows}
    state = rebuild_state(manifest, rows)
    families = families_of(manifest)
    per_family = int(manifest["attempts_per_family"])
    budgets = dict(manifest["budgets"])
    min_defined = int(manifest["admission"]["min_defined_probes"])

    execution = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 "git_head": _git_head(), "code_hashes_at_start": code_at_start,
                 "manifest_sha256": _sha_file(MANIFEST),
                 "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
                 "python": platform.python_version(), "resources_at_start": _resource_snapshot(),
                 "resumed_from_rows": len(rows)}
    EXECUTION.write_text(json.dumps(execution, indent=1, sort_keys=True))

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
                    budgets=budgets, row_index=attempt, min_defined_probes=min_defined)
            except Exception as error:                            # noqa: BLE001
                outcome = f"{V2C.INFRA_PREFIX}{type(error).__name__}"
                episode, evidence = None, {"infra_error": repr(error)[:300], "units": {}}
                state.record(digest=CV.digest(schema), regime=regime, outcome=outcome,
                             concrete_digest=None, demo_digest=None)
            row = {"family": list(family), "family_text": family_text, "attempt": attempt,
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
        scientific = {k: v for k, v in outcomes.items() if not k.startswith(V2C.INFRA_PREFIX)}
        infra = {k: v for k, v in outcomes.items() if k.startswith(V2C.INFRA_PREFIX)}
        admitted = [r for r in frows if r["outcome"] == V2C.ADMITTED]
        report["families"][text] = {
            "family": list(family), "attempts": len(frows),
            "admitted_attempts": len(admitted),
            "admitted_distinct_schemas": len({r["schema_digest"] for r in admitted}),
            "feasible": len(admitted) > 0,
            "scientific_outcomes": dict(sorted(scientific.items())),
            "infrastructure_errors": dict(sorted(infra.items())),
            "wall_clock_truncations": sum(1 for r in frows if r.get("truncated_by_wall_clock")),
            "irreducibility_inconclusive": scientific.get("irreducibility_inconclusive", 0),
            "seconds": round(sum(r["seconds"] for r in frows), 1)}
    fams = report["families"]
    report["decision_a_gates"] = {
        "g2_multi_block_target": any(v["feasible"] and len(v["family"]) > 1 for v in fams.values()),
        "g3_repeated_select_target": any(v["feasible"] and 2 in v["family"] for v in fams.values()),
        "g4_zero_select_block_in_multi_block_target": any(
            v["feasible"] and len(v["family"]) > 1 and 0 in v["family"] for v in fams.values()),
        "g5_both_holdout_families": all(fams[CV.family_text(f)]["feasible"] for f in holdout),
        "families_with_admissions": [k for k, v in fams.items() if v["feasible"]],
        "families_without_admissions": [k for k, v in fams.items() if not v["feasible"]],
    }
    code_at_end = V2C.code_hashes_v2c()
    report["execution"] = dict(execution, finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                               code_hashes_at_end=code_at_end,
                               code_unchanged_during_run=code_at_end == execution["code_hashes_at_start"],
                               resources_at_end=_resource_snapshot(), seconds_this_process=round(seconds, 1))
    report["attempts_sha256"] = _sha_file(ATTEMPTS)
    RESULTS.write_text(json.dumps(report, indent=2, sort_keys=True))
    print("V2C_CENSUS_DONE", json.dumps(report["decision_a_gates"]), flush=True)
    return report


if __name__ == "__main__":
    run()
