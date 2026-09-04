"""Independent audit of the Item-2 Block-B constructive pilot.

Recomputes rather than trusting stored booleans wherever feasible. Emits
outputs/tti/constructive_pilot_audit.json with an explicit PASS/FAIL verdict.
A failed mandatory check is never downgraded to a warning.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from geocat_arc.object_reasoning import meta_ast as M          # noqa: E402
from geocat_arc.object_reasoning import meta_induction as MI   # noqa: E402
from cora_tti import constructive_dataset as CD                # noqa: E402
from cora_tti import constructive_vocabulary as CV             # noqa: E402

OUT = ROOT / "outputs" / "tti"
SLOTS = OUT / "constructive_pilot_slots"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit() -> dict:
    checks, notes = {}, {}

    #  1-2 protocol and generation manifest integrity
    pinned = (OUT / "constructive_protocol_manifest_hash.txt").read_text().split()[0]
    checks["protocol_manifest_hash"] = (
        _sha(OUT / "constructive_protocol_manifest.json") == pinned)
    gen_pinned = (OUT / "constructive_pilot_generation_manifest_hash.txt"
                  ).read_text().split()[0]
    checks["generation_manifest_hash"] = (
        _sha(OUT / "constructive_pilot_generation_manifest.json") == gen_pinned)

    records = [json.loads(p.read_text()) for p in sorted(SLOTS.glob("slot*.json"))]
    notes["slots_found"] = len(records)
    checks["every_slot_has_terminal_outcome"] = all(
        r["attempts"] and all(a["outcome"] for a in r["attempts"]) for r in records)
    checks["no_slot_exceeded_attempt_cap"] = all(
        r["attempts_used"] <= r["max_attempts"] for r in records)
    checks["slot_records_pin_generation_manifest"] = all(
        r.get("generation_manifest_hash") == gen_pinned for r in records)

    admitted = [r for r in records if r["admitted"]]
    notes["admitted"] = len(admitted)
    notes["attempted_targets"] = sum(r["attempts_used"] for r in records)

    #  rejection accounting: attempted == admitted + rejected (+ infra, separate)
    science, infra = Counter(), Counter()
    for record in records:
        for attempt in record["attempts"]:
            outcome = attempt["outcome"]
            if outcome == CD.ADMITTED:
                continue
            (infra if outcome.startswith("infra_exception") else science)[outcome] += 1
    notes["rejections_by_code"] = dict(sorted(science.items()))
    notes["infrastructure_failures"] = dict(sorted(infra.items()))
    checks["rejection_codes_are_frozen_vocabulary"] = set(science) <= set(
        CD.REJECTION_CODES)
    checks["accounting_reconciles"] = (
        notes["attempted_targets"] == len(admitted) + sum(science.values())
        + sum(infra.values()))

    #  per-admitted-row recomputation
    digests, row_checks = [], []
    for record in admitted:
        episode = record["episode"]
        schema = M.ast_from_json(episode["target_schema_json"])
        ok, code = CV.validate(schema)
        family = CV.family(schema)
        demos = episode["demonstrations"]
        pairs = [(np.asarray(d["input"]), np.asarray(d["output"])) for d in demos]
        fitted = MI.fit_induced_slots(schema, pairs)
        row = {
            "slot": record["slot"],
            "parses_and_valid": ok,
            "family_matches_request": list(family) == record["requested_family"],
            "family_permitted_for_split": (
                not CV.is_banned_target_family(family)
                and (CV.is_holdout_family(family)
                     if record["regime"] == "structural_holdout"
                     else not CV.is_holdout_family(family))),
            "at_least_three_demos": len(demos) >= 3,
            "outputs_differ_from_inputs": all(
                not np.array_equal(a, b) for a, b in pairs),
            "stored_output_equals_fresh_execution": all(
                (lambda r: r is not None and np.array_equal(r, b))(
                    M.evaluate(M.ast_from_json(episode["target_concrete_json"]),
                               a, MI.descriptors))
                for a, b in pairs),
            "ordinary_learner_reproduces": (
                fitted is not None
                and MI.observational_signature(fitted, pairs) is not None),
            "model_view_clean": True,
        }
        trusted = CD.TrustedEpisode(**episode)
        view = CD.to_model_view(trusted, record["slot"])
        row["model_view_clean"] = CD.scan_model_view(view, trusted) == []
        row_checks.append(row)
        digests.append(episode["target_digest"])

    checks["all_admitted_rows_pass_recomputation"] = all(
        all(v for k, v in row.items() if k != "slot") for row in row_checks)
    checks["digests_unique"] = len(digests) == len(set(digests))
    train_digests = {r["episode"]["target_digest"] for r in admitted
                     if r["split"] == "train"}
    test_a = [r for r in admitted if r["regime"] == "ast_holdout"]
    checks["ast_holdout_disjoint_from_train"] = all(
        r["episode"]["target_digest"] not in train_digests for r in test_a)
    train_val_families = {tuple(r["episode"]["structural_family"]) for r in admitted
                          if r["split"] in ("train", "val")}
    checks["structural_holdout_families_absent_from_train_val"] = not (
        train_val_families & {tuple(f) for f in CV.vocab()["holdout_families"]
                              if isinstance(f, tuple)} )
    checks["banned_families_absent"] = not any(
        CV.is_banned_target_family(tuple(r["episode"]["structural_family"]))
        for r in admitted)
    checks["regime_c_absent_and_declared_infeasible"] = (
        "INFEASIBLE" in CV.manifest()["interface_holdout"]
        and not any(r["regime"] == "interface_holdout" for r in records))

    #  achieved counts against the frozen request
    requested = Counter((r["split"], r["regime"]) for r in records)
    achieved = Counter((r["split"], r["regime"]) for r in admitted)
    notes["requested_by_split"] = {f"{k[0]}/{k[1]}": v for k, v in sorted(requested.items())}
    notes["achieved_by_split"] = {f"{k[0]}/{k[1]}": v for k, v in sorted(achieved.items())}
    fam_req = Counter(tuple(r["requested_family"]) for r in records)
    fam_ach = Counter(tuple(r["episode"]["structural_family"]) for r in admitted)
    notes["requested_by_family"] = {CV.family_text(k): v for k, v in sorted(fam_req.items())}
    notes["achieved_by_family"] = {CV.family_text(k): v for k, v in sorted(fam_ach.items())}

    mandatory = [k for k in checks if k != "all_admitted_rows_pass_recomputation"
                 or admitted]
    verdict = "PASS" if all(checks[k] for k in mandatory) else "FAIL"
    return {"verdict": verdict, "checks": checks, "notes": notes,
            "per_row": row_checks,
            "code_hash": CD._code_hash()}


if __name__ == "__main__":
    report = audit()
    (OUT / "constructive_pilot_audit.json").write_text(
        json.dumps(report, indent=1, sort_keys=True))
    print(json.dumps({"verdict": report["verdict"],
                      "failed": [k for k, v in report["checks"].items() if not v],
                      "notes": report["notes"]}, indent=1))
