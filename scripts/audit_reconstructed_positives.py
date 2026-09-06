"""Audit every recoverable positive of the original protocol-v2 census.

Evidence-closure directive, section 10. This is an ANALYSIS OF AN ALREADY
OBSERVED EXPLORATORY RESULT, never prospective validation.

What is auditable, and what is not
    The original runner retained only per-family outcome counts and two example
    summaries per family, so no original positive has retained per-attempt
    evidence. The census was additionally found to be non-reproducible from its
    seeds (the v1.1 generator's colour term uses Python's salted hash), so even
    re-execution under the pinned code cannot recover the original attempt
    identities. Consequently:

      * every ORIGINAL admitted attempt is UNVERIFIABLE_FROM_RETAINED_EVIDENCE;
      * what CAN be audited is each RECONSTRUCTED positive, under an explicit
        hash-seed label, and that is what this script does.

    The original admission labels are never overwritten. The audit is stored
    beside them.

Checks applied to each reconstructed positive (directive section 10)
    grammar validity                 re-validated from the stored schema
    exact target replay              re-executed from the stored fitted program
    target-only metadata isolation   the v1.1 leak scanner, re-run
    common baseline/fitter authority the fitter identity and OPTIONS of both paths
    baseline failure                 re-run under the single identified baseline
    historical overlap               against the derived v1.1 exclusion set
    uniqueness                       across all reconstructions and within each
    probe coverage                   defined probes for target and comparisons
    direct and refitted ablations    the v2c four-outcome irreducibility contract
    TFG provenance                   which reasoner produced the stored graph
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M            # noqa: E402
from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_probes as CP                   # noqa: E402
from cora_tti import constructive_v2c as V2C                     # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import meta_baseline as MB                         # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

STATUSES = ("VERIFIED_WITHIN_STATED_SCOPE", "DOWNGRADED", "FAILED_AUDIT",
            "UNVERIFIABLE_FROM_RETAINED_EVIDENCE")

parser = argparse.ArgumentParser()
parser.add_argument("--reconstruction-root",
                    default=str(ROOT / "outputs" / "tti" / "constructive_v2_reconstruction"))
parser.add_argument("--original",
                    default=str(ROOT / "outputs" / "tti" / "constructive_v2_feasibility_results.json"))
parser.add_argument("--v1-exclusion",
                    default=str(ROOT / "outputs" / "tti" / "constructive_v1_1_target_exclusion.json"))
parser.add_argument("--out",
                    default=str(ROOT / "outputs" / "tti" / "constructive_v2_corrected"
                               / "original_positives_audit.json"))
args = parser.parse_args()

CONFIG = MB.BaselineConfig()
V1_EXCLUSION = set(json.loads(Path(args.v1_exclusion).read_text())["digests"])
ORIGINAL = json.loads(Path(args.original).read_text())


def audit_episode(episode: dict, seed_label: str, all_digests: Counter) -> dict:
    checks: dict = {}
    downgrades, failures = [], []

    schema = M.ast_from_json(episode["target_schema_json"])
    fitted = M.ast_from_json(episode["target_fitted_json"])
    pairs = [(np.asarray(d["input"], dtype=int), np.asarray(d["output"], dtype=int))
             for d in episode["demonstrations"]]

    #  1. grammar validity
    ok, code = CV.validate(schema)
    checks["grammar_valid"] = {"pass": bool(ok), "code": code}
    if not ok:
        failures.append("grammar_invalid")

    #  2. digest integrity and family
    digest = CV.digest(schema)
    checks["digest_matches_record"] = {"pass": digest == episode["target_digest"],
                                       "recomputed": digest}
    if digest != episode["target_digest"]:
        failures.append("digest_mismatch")
    family = CV.family(schema)
    checks["family_matches_record"] = {"pass": list(family) == episode["structural_family"],
                                       "recomputed": list(family)}

    #  3. exact target replay from the STORED artifacts
    replays, undefined = 0, 0
    for grid_in, grid_out in pairs:
        rendered = V2C._evaluate(fitted, grid_in)
        if rendered is None:
            undefined += 1
        elif np.array_equal(rendered, grid_out):
            replays += 1
    checks["exact_replay"] = {"pass": replays == len(pairs), "replayed": replays,
                              "demonstrations": len(pairs), "undefined": undefined}
    if replays != len(pairs):
        failures.append("replay_failed")

    #  4. target-only metadata isolation (the v1.1 scanner, re-run)
    trusted = CD.TrustedEpisode(
        episode_id=episode["episode_id"], split=episode["split"], regime=episode["regime"],
        generation_seed=episode["generation_seed"], demonstrations=episode["demonstrations"],
        target_schema_json=episode["target_schema_json"],
        target_concrete_json=episode["target_concrete_json"],
        target_tokens=episode["target_tokens"], target_digest=episode["target_digest"],
        structural_family=episode["structural_family"], block_count=episode["block_count"],
        stage_count=episode["stage_count"], node_count=episode["node_count"],
        schema_mdl=episode["schema_mdl"], slot_declarations=episode["slot_declarations"],
        fitted_slot_values={}, tfg=episode["tfg"], tfg_digest=episode["tfg_digest"],
        base_search_evidence=episode.get("base_search_evidence", {}),
        baseline_shape_audit=episode.get("base_search_evidence", {}),
        target_fit_evidence={"fitted": True, "exact_on_all_demos": True},
        probe_fingerprint=episode["probe_fingerprint"], diagnostics={},
        protocol_hash=episode.get("protocol_v2_hash", ""), code_hash=episode.get("code_hash", ""))
    view = CD.to_model_view(trusted, 0)
    findings = CD.scan_model_view(view, trusted)
    checks["model_view_isolation"] = {"pass": not findings, "findings": findings}
    if findings:
        failures.append("leak")

    #  5-6. common fitting authority, and baseline failure under ONE reasoner
    refit = SF.fit_outcome(schema, pairs, require_exact_replay=True)
    checks["target_refits_under_current_fitter"] = {
        "pass": refit["status"] == "EXACT_DEMONSTRATION_FIT", "status": refit["status"],
        "code": refit["code"]}
    if refit["status"] != "EXACT_DEMONSTRATION_FIT":
        downgrades.append(f"target_refit:{refit['status']}:{refit['code']}")
    trace = MB.run_baseline(pairs, CONFIG)
    checks["baseline_failure"] = {
        "pass": not trace.exact, "exact_baselines": len(trace.exact),
        "constraint_consistent": len(trace.constraint_consistent),
        "work_done": trace.work_done, "truncated": trace.truncated,
        "census": dict(sorted(trace.census.items()))}
    if trace.exact:
        failures.append("baseline_solves_it_under_the_single_identified_reasoner")
    checks["fitter_authority_shared"] = {
        "pass": trace.fitter_identity == SF.fitter_identity(),
        "baseline_fitter": trace.fitter_identity[:16],
        "target_fitter": SF.fitter_identity()[:16],
        "options_equal": SF.fitter_options(True) == dict(CONFIG.strict_options),
        "recorded_options": SF.fitter_options(True)}
    if not checks["fitter_authority_shared"]["options_equal"]:
        downgrades.append("fitter_options_differ")

    #  7. historical overlap and uniqueness
    checks["historical_overlap"] = {"pass": digest not in V1_EXCLUSION,
                                    "in_v1_1_attempted_set": digest in V1_EXCLUSION}
    if digest in V1_EXCLUSION:
        downgrades.append("overlaps_v1_1_attempted_targets")
    checks["uniqueness"] = {"pass": all_digests[digest] == 1,
                            "times_admitted_across_reconstructions": all_digests[digest]}

    #  8. probe coverage and witness separation, recomputed
    target_fp, target_status = CP.fingerprint_with_diagnostics(fitted, V2C._evaluate)
    defined = sum(1 for s in target_status if s == "OK")
    equivalent, both_defined = 0, []
    for _s, program_b, _sig in trace.constraint_consistent:
        fp_b, status_b = CP.fingerprint_with_diagnostics(program_b, V2C._evaluate)
        both_defined.append(sum(1 for a, b in zip(status_b, target_status)
                                if a == "OK" and b == "OK"))
        if fp_b == target_fp:
            equivalent += 1
    checks["probe_coverage"] = {
        "pass": defined > 0, "target_defined_probes": defined,
        "probe_count": len(target_status),
        "fingerprint_matches_record": target_fp == episode["probe_fingerprint"],
        "comparisons_with_both_defined_min": min(both_defined) if both_defined else None,
        "comparisons_with_both_defined_max": max(both_defined) if both_defined else None}
    if defined == 0:
        downgrades.append("target_defined_on_zero_probes")
    checks["witness_separation"] = {"pass": equivalent == 0,
                                    "witness_equivalent_baselines": equivalent}
    if equivalent:
        failures.append("witness_not_separated_under_the_single_identified_reasoner")

    #  9. irreducibility under the CORRECTED contract
    audit = V2C.irreducibility_audit_v2c(schema, fitted, pairs, target_fp, target_status)
    checks["irreducibility"] = {
        "pass": not audit["reducible"] and not audit["inconclusive"],
        "counts": audit["counts"], "reducible": audit["reducible"],
        "inconclusive": audit["inconclusive"],
        "original_metric_preserved": episode.get("irreducibility"),
        "outcomes": [{"kind": a["kind"], "index": a.get("index"),
                      "outcome": a.get("outcome"), "reason": a.get("reason", "")[:200]}
                     for a in audit["ablations"]]}
    if audit["reducible"]:
        failures.append("locally_reducible_under_the_corrected_contract")
    elif audit["inconclusive"]:
        downgrades.append("irreducibility_inconclusive_under_the_corrected_contract")

    #  10. TFG provenance
    execution_nodes = [n for n in episode["tfg"]["nodes"] if n.get("kind") == "execution"]
    attrs = execution_nodes[0]["attrs"] if execution_nodes else {}
    carries_config = "baseline_config" in attrs and "trace_config" in attrs
    frontier_ops = {n["attrs"].get("op") for n in episode["tfg"]["nodes"]
                    if n.get("kind") == "frontier_term"}
    checks["tfg_provenance"] = {
        "pass": bool(carries_config),
        "carries_baseline_configuration": bool(carries_config),
        "produced_by": ("the identified meta baseline" if carries_config
                        else "the blind-runtime trace search, a DIFFERENT reasoner from the "
                             "baseline used for admission"),
        "frontier_root_ops": sorted(o for o in frontier_ops if o),
        "outcome_census": attrs.get("outcome_census")}
    if not carries_config:
        downgrades.append("tfg_from_a_different_reasoner_than_the_admission_baseline")

    status = ("FAILED_AUDIT" if failures else
              "DOWNGRADED" if downgrades else "VERIFIED_WITHIN_STATED_SCOPE")
    return {"episode_id": episode["episode_id"], "hash_seed": seed_label,
            "identity_label": "RECONSTRUCTED_FROM_PINNED_GENERATOR",
            "family": episode["structural_family"], "target_digest": digest,
            "original_admission_label": "ADMITTED (original run, attempt identity unverifiable)",
            "audit_status": status, "failures": failures, "downgrades": downgrades,
            "checks": checks}


def main() -> dict:
    root = Path(args.reconstruction_root)
    runs = sorted(p for p in root.glob("hashseed_*") if (p / "summary.json").exists())
    all_digests: Counter = Counter()
    episodes: list = []
    for run in runs:
        label = run.name.replace("hashseed_", "")
        for path in sorted((run / "admitted").glob("*.json")):
            episode = json.loads(path.read_text())
            all_digests[episode["target_digest"]] += 1
            episodes.append((label, path, episode))

    audits = [audit_episode(episode, label, all_digests) for label, _path, episode in episodes]
    by_status = Counter(a["audit_status"] for a in audits)
    by_family = defaultdict(Counter)
    for a in audits:
        by_family[CV.family_text(tuple(a["family"]))][a["audit_status"]] += 1
    downgrade_reasons = Counter(r.split(":")[0] for a in audits for r in a["downgrades"])
    failure_reasons = Counter(a_f for a in audits for a_f in a["failures"])

    #  the ORIGINAL positives: what the retained evidence can and cannot support
    retained = []
    reconstructed_digests = {a["target_digest"][:16]: a for a in audits}
    for family_text, record in ORIGINAL["families"].items():
        for example in record.get("examples", []):
            match = reconstructed_digests.get(example["digest"])
            retained.append({
                "family": family_text, "digest_prefix": example["digest"],
                "retained_fields": sorted(example),
                "audit_status": "UNVERIFIABLE_FROM_RETAINED_EVIDENCE",
                "reason": "the original run retained no per-attempt evidence and is not "
                          "reproducible from its seeds (salted hash in the generator); this "
                          "digest is a schema identity, not a record of the attempt",
                "same_schema_admitted_in_a_reconstruction": bool(match),
                "reconstruction_audit_status": match["audit_status"] if match else None})

    report = {
        "scope": "analysis of an already observed exploratory result; NOT prospective validation",
        "original_run": {
            "results_sha256": hashlib.sha256(Path(args.original).read_bytes()).hexdigest(),
            "admitted_attempts": sum(v["admitted"] for v in ORIGINAL["families"].values()),
            "per_family_admitted": {k: v["admitted"] for k, v in ORIGINAL["families"].items()},
            "auditable_positives": 0,
            "audit_status_of_every_original_positive": "UNVERIFIABLE_FROM_RETAINED_EVIDENCE",
            "retained_example_summaries": retained},
        "reconstructed_positives": {
            "identity_label": "RECONSTRUCTED_FROM_PINNED_GENERATOR",
            "runs_audited": [p.name for p in runs],
            "episodes_audited": len(audits),
            "distinct_schemas": len(all_digests),
            "admitted_in_all_runs": sum(1 for v in all_digests.values() if v == len(runs)),
            "admitted_in_exactly_one_run": sum(1 for v in all_digests.values() if v == 1),
            "by_status": dict(by_status),
            "by_family": {k: dict(v) for k, v in by_family.items()},
            "downgrade_reasons": dict(downgrade_reasons),
            "failure_reasons": dict(failure_reasons)},
        "audits": audits,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=1, sort_keys=True, default=str)
    out.write_text(text)
    report["sha256"] = hashlib.sha256(text.encode()).hexdigest()
    return report


if __name__ == "__main__":
    result = main()
    print(json.dumps(result["reconstructed_positives"], indent=1))
    print("original positives:", result["original_run"]["audit_status_of_every_original_positive"])
    print("sha256:", result["sha256"])
