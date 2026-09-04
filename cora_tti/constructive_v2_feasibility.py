"""Protocol v2 feasibility census (directive sections 14 and 15).

Method development on disposable synthetic fixtures. Produces NO training,
validation or test rows, touches no DEV or HOLDOUT data, and reads nothing
from the live Step-B experiment.

For every declared target family, mechanically generate targets with the frozen
deterministic sampler and ask whether at least one satisfies the full v2
admission law R1 to R12. Positive family evidence must come from the generator,
never from a hand-authored target chosen after seeing failures.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from cora_tti import constructive_dataset as CD                  # noqa: E402
from cora_tti import constructive_v2_dataset as V2               # noqa: E402
from cora_tti import constructive_vocabulary as CV               # noqa: E402
from cora_tti import scoped_slot_fitting as SF                   # noqa: E402

OUT = ROOT / "outputs" / "tti"
MANIFEST = OUT / "constructive_v2_feasibility_manifest.json"
RESULTS = OUT / "constructive_v2_feasibility_results.json"

TRAINING_FAMILIES = ((0, 0), (1, 0), (0, 1), (1, 1), (0, 0, 0))
HOLDOUT_FAMILIES = ((2,), (2, 1))
SEED_NAMESPACE = 5_100_000
ATTEMPTS_PER_FAMILY = 120
BUDGETS = {"per_target_s": 120.0, "tfg_s": 2.0}


def census() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    families = [tuple(f) for f in
                [*manifest["families_tested"]["training"],
                 *manifest["families_tested"]["structural_holdout"]]]
    report = {"manifest_sha256": hashlib.sha256(
        MANIFEST.read_text().encode()).hexdigest(),
        "fitter_identity": SF.fitter_identity(),
        "attempts_per_family": ATTEMPTS_PER_FAMILY,
        "families": {}}
    for family in families:
        holdout = CV.is_holdout_family(family)
        regime = "structural_holdout" if holdout else "train_pool"
        outcomes, admitted, examples = {}, 0, []
        started = time.monotonic()
        for attempt in range(ATTEMPTS_PER_FAMILY):
            seed = SEED_NAMESPACE + attempt * 7919 + len(family) * 1013 \
                + sum(family) * 37
            schema = CD.sample_target(seed, family)
            try:
                outcome, episode, evidence = V2.evaluate_target_v2(
                    schema, seed=seed, split="feasibility", regime=regime,
                    allowed_families=[family], seen_digests=set(),
                    seen_train_digests=set(), v1_exclusion=set(),
                    budgets=BUDGETS, row_index=attempt)
            except Exception as error:                       # noqa: BLE001
                outcome = f"{V2.INFRA_PREFIX}{type(error).__name__}"
                episode = None
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            if outcome == V2.ADMITTED:
                admitted += 1
                if len(examples) < 2:
                    examples.append({
                        "digest": episode["target_digest"][:16],
                        "blocks": episode["block_count"],
                        "mdl": episode["schema_mdl"],
                        "demos": len(episode["demonstrations"]),
                        "slot_occurrences": len(episode["slot_occurrences"]),
                        "base_exact": episode["base_search_evidence"]["exact"],
                        "base_fitted": episode["base_search_evidence"]["fitted"],
                        "prefixes": [o["local_prefix"]
                                     for o in episode["slot_occurrences"]]})
        report["families"][CV.family_text(family)] = {
            "family": list(family), "regime": regime,
            "attempts": ATTEMPTS_PER_FAMILY, "admitted": admitted,
            "feasible": admitted > 0,
            "outcomes": dict(sorted(outcomes.items())),
            "seconds": round(time.monotonic() - started, 1),
            "examples": examples}
        print(f"{CV.family_text(family):8} admitted={admitted:3} "
              f"{json.dumps(dict(sorted(outcomes.items())))} "
              f"{report['families'][CV.family_text(family)]['seconds']}s",
              flush=True)

    #  directive section 15 go/no-go gates
    fams = report["families"]
    multi = [k for k, v in fams.items() if v["feasible"] and len(v["family"]) > 1]
    repeated_select = [k for k, v in fams.items()
                       if v["feasible"] and 2 in v["family"]]
    zero_select_in_multi = [k for k, v in fams.items()
                            if v["feasible"] and len(v["family"]) > 1
                            and 0 in v["family"]]
    report["gates"] = {
        "g2_multi_block_target": bool(multi),
        "g3_repeated_select_target": bool(repeated_select),
        "g4_zero_select_block_in_multi_block_target": bool(zero_select_in_multi),
        "g5_both_holdout_families": all(
            fams[CV.family_text(f)]["feasible"] for f in HOLDOUT_FAMILIES),
        "training_families_feasible": [k for k, v in fams.items()
                                       if v["feasible"] and not CV.is_holdout_family(
                                           tuple(v["family"]))],
        "infeasible_families": [k for k, v in fams.items() if not v["feasible"]],
    }
    return report


if __name__ == "__main__":
    result = census()
    RESULTS.write_text(json.dumps(result, indent=2, sort_keys=True))
    print("FEASIBILITY_CENSUS_DONE", json.dumps(result["gates"]), flush=True)
